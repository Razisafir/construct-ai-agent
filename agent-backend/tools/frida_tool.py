"""Frida Tool — dynamic instrumentation toolkit for runtime analysis.

Requires frida-python (pip install frida-tools) and optionally the
frida binary on the system PATH for device enumeration.

This tool provides a Python interface to Frida for:
- Listing running processes on attached devices
- Attaching to processes and injecting JavaScript hooks
- Bypassing SSL pinning and root detection on mobile apps
- Tracing cryptographic operations and network traffic
- Generating hook scripts from Ghidra analysis results
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import frida

    FRIDA_PYTHON_AVAILABLE = True
except ImportError:
    FRIDA_PYTHON_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SCRIPT_TIMEOUT: int = 600
"""Absolute maximum seconds a Frida script is allowed to run."""

DEFAULT_SCRIPT_TIMEOUT: int = 60
"""Default timeout for a Frida script session."""

SYSTEM_PROCESSES_BLOCKED: set[str] = {
    "kernel",
    "init",
    "systemd",
    "launchd",
    "kthreadd",
    "ksoftirqd",
    "rcu_sched",
    "migration",
}
"""Process names that must never be attached to — doing so would risk
system stability or a kernel panic."""

# ---------------------------------------------------------------------------
# Built-in Frida script templates
# ---------------------------------------------------------------------------

SCRIPT_TEMPLATES: Dict[str, str] = {
    "ssl_pinning_bypass": r"""
"use strict";

// SSL Pinning Bypass — Android + iOS
// Hooks common trust-manager and certificate-verification APIs so that
// any certificate is accepted regardless of pinning configuration.

if (Java.available) {
    Java.perform(function () {
        // --- Android: TrustManagerFactory ---
        var TMF = Java.use("javax.net.ssl.TrustManagerFactory");
        TMF.init.overload("javax.net.ssl.KeyManager[]", "javax.net.ssl.TrustManager[]")
            .implementation = function (km, tm) {
                console.log("[ssl-pinning] TrustManagerFactory.init bypassed");
                this.init(km, null);
            };

        // --- Android: SSLContext ---
        var SSLCtx = Java.use("javax.net.ssl.SSLContext");
        SSLCtx.init.overload(
            "[Ljavax.net.ssl.KeyManager;",
            "[Ljavax.net.ssl.TrustManager;",
            "java.security.SecureRandom"
        ).implementation = function (km, tm, sr) {
            console.log("[ssl-pinning] SSLContext.init bypassed");
            this.init(km, null, sr);
        };

        // --- Android: OkHttp CertificatePinner ---
        try {
            var CertPinner = Java.use("okhttp3.CertificatePinner");
            CertPinner.check.overload("java.lang.String", "java.util.List")
                .implementation = function (hostname, peerCerts) {
                    console.log("[ssl-pinning] OkHttp CertificatePinner.check bypassed for " + hostname);
                };
        } catch (e) {
            console.log("[ssl-pinning] OkHttp not found, skipping CertificatePinner hook");
        }

        // --- Android: X509TrustManager ---
        var X509TM = Java.use("javax.net.ssl.X509TrustManager");
        Java.choose("javax.net.ssl.X509TrustManager", {
            onMatch: function (instance) {
                console.log("[ssl-pinning] Found X509TrustManager instance");
            },
            onComplete: function () {}
        });
    });
}

if (ObjC.available) {
    // --- iOS: NSURLSession trust evaluation ---
    var SecTrustEvaluate = Module.findExportByName("Security", "SecTrustEvaluate");
    if (SecTrustEvaluate) {
        Interceptor.replace(SecTrustEvaluate, new NativeCallback(function (trust, result) {
            console.log("[ssl-pinning] SecTrustEvaluate bypassed");
            Memory.writeU8(result, 1); // kSecTrustResultProceed
            return 0; // errSecSuccess
        }, "int", ["pointer", "pointer"]));
    }

    var SecTrustEvaluateWithError = Module.findExportByName("Security", "SecTrustEvaluateWithError");
    if (SecTrustEvaluateWithError) {
        Interceptor.replace(SecTrustEvaluateWithError, new NativeCallback(function (trust, error) {
            console.log("[ssl-pinning] SecTrustEvaluateWithError bypassed");
            if (error && !error.isNull()) {
                Memory.writePointer(error, ptr(0));
            }
            return 1; // true
        }, "bool", ["pointer", "pointer"]));
    }
}

console.log("[ssl-pinning] SSL pinning bypass script loaded");
""",
    "root_detection_bypass": r"""
"use strict";

// Root / Jailbreak Detection Bypass — Android + iOS
// Hooks common root-detection APIs so the app believes it is running
// on an unrooted / unjailbroken device.

if (Java.available) {
    Java.perform(function () {
        // --- Android: File.exists() for su binary ---
        var File = Java.use("java.io.File");
        File.exists.implementation = function () {
            var path = this.getAbsolutePath();
            var suspicious = ["/sbin/su", "/system/bin/su", "/system/xbin/su",
                              "/data/local/xbin/su", "/data/local/bin/su",
                              "/system/sd/xbin/su", "/su/bin/su",
                              "/magisk/.core/bin/su"];
            if (suspicious.indexOf(path) >= 0) {
                console.log("[root-bypass] File.exists() bypassed for " + path);
                return false;
            }
            return this.exists();
        };

        // --- Android: PackageManager check for root apps ---
        var PM = Java.use("android.app.ApplicationPackageManager");
        PM.getPackageInfo.overload("java.lang.String", "int")
            .implementation = function (pkg, flags) {
                var rootPackages = ["com.noshufou.android.su", "eu.chainfire.supersu",
                                    "com.topjohnwu.magisk", "com.koushikdutta.superuser"];
                if (rootPackages.indexOf(pkg) >= 0) {
                    console.log("[root-bypass] PackageManager.getPackageInfo bypassed for " + pkg);
                    throw Java.use("android.content.pm.PackageManager$NameNotFoundException").$new(pkg);
                }
                return this.getPackageInfo(pkg, flags);
            };

        // --- Android: Build.TAGS test-keys ---
        var Build = Java.use("android.os.Build");
        var origTags = Build.TAGS.value;
        if (origTags && origTags.indexOf("test-keys") >= 0) {
            Build.TAGS.value = "release-keys";
            console.log("[root-bypass] Build.TAGS patched from '" + origTags + "' to 'release-keys'");
        }

        // --- Android: SafetyNet Attestation (basic) ---
        try {
            var SafetyNetCls = Java.use("com.google.android.gms.safetynet.SafetyNetClient");
            console.log("[root-bypass] SafetyNet class found — hooking attestation");
        } catch (_) {
            console.log("[root-bypass] SafetyNet class not found, skipping");
        }
    });
}

if (ObjC.available) {
    // --- iOS: Jailbreak file checks ---
    var fopen = Module.findExportByName(null, "fopen");
    if (fopen) {
        Interceptor.attach(fopen, {
            onEnter: function (args) {
                var path = args[0].readUtf8String();
                var jailbreakPaths = ["/Applications/Cydia.app", "/Library/MobileSubstrate",
                                      "/bin/bash", "/usr/sbin/sshd", "/etc/apt",
                                      "/private/var/lib/apt", "/usr/bin/ssh"];
                for (var i = 0; i < jailbreakPaths.length; i++) {
                    if (path && path.indexOf(jailbreakPaths[i]) === 0) {
                        console.log("[root-bypass] fopen redirect: " + path);
                        this.redirectPath = true;
                        break;
                    }
                }
            },
            onLeave: function (retval) {
                if (this.redirectPath) {
                    retval.replace(ptr(0));
                }
            }
        });
    }

    // --- iOS: canOpenURL for cydia ---
    var UIApplication = ObjC.classes.UIApplication;
    if (UIApplication) {
        var canOpen = UIApplication["- canOpenURL:"];
        Interceptor.attach(canOpen.implementation, {
            onLeave: function (retval) {
                if (retval.toInt32() === 1) {
                    console.log("[root-bypass] canOpenURL returned true — forcing false");
                    retval.replace(ptr(0));
                }
            }
        });
    }
}

console.log("[root-bypass] Root / jailbreak detection bypass loaded");
""",
    "crypto_tracer": r"""
"use strict";

// Crypto Tracer — intercepts common cryptographic API calls
// Hooks AES, RSA, MD5, SHA1/256 operations on Android and prints
// keys, plaintext, and ciphertext.

if (Java.available) {
    Java.perform(function () {
        // --- AES Cipher ---
        var Cipher = Java.use("javax.crypto.Cipher");
        Cipher.doFinal.overload("[B").implementation = function (input) {
            var algo = this.getAlgorithm();
            var mode = this.getOpmode();
            var result = this.doFinal(input);
            var tag = (mode === 1) ? "ENCRYPT" : "DECRYPT";
            console.log("[crypto] AES " + tag + " algorithm=" + algo);
            console.log("[crypto]   input (" + input.length + " bytes): " + bytesToHex(input));
            console.log("[crypto]   output (" + result.length + " bytes): " + bytesToHex(result));
            return result;
        };

        // --- SecretKeySpec (captures the key) ---
        var SecretKeySpec = Java.use("javax.crypto.spec.SecretKeySpec");
        SecretKeySpec.$init.overload("[B", "java.lang.String")
            .implementation = function (keyBytes, algo) {
                console.log("[crypto] SecretKeySpec algo=" + algo + " key=" + bytesToHex(keyBytes));
                return this.$init(keyBytes, algo);
            };

        // --- MessageDigest (MD5, SHA-1, SHA-256) ---
        var MessageDigest = Java.use("java.security.MessageDigest");
        MessageDigest.update.overload("[B").implementation = function (input) {
            console.log("[crypto] MessageDigest " + this.getAlgorithm() +
                        " update (" + input.length + " bytes): " + bytesToHex(input));
            return this.update(input);
        };
        MessageDigest.digest.overload().implementation = function () {
            var result = this.digest();
            console.log("[crypto] MessageDigest " + this.getAlgorithm() +
                        " digest: " + bytesToHex(result));
            return result;
        };

        // --- RSA Cipher ---
        Cipher.doFinal.overload("[B", "int").implementation = function (input, offset) {
            var algo = this.getAlgorithm();
            var mode = this.getOpmode();
            var result = this.doFinal(input, offset);
            var tag = (mode === 1) ? "ENCRYPT" : "DECRYPT";
            console.log("[crypto] RSA " + tag + " algorithm=" + algo);
            console.log("[crypto]   input (" + input.length + " bytes): " + bytesToHex(input));
            console.log("[crypto]   output (" + result.length + " bytes): " + bytesToHex(result));
            return result;
        };

        // --- Mac (HMAC) ---
        var Mac = Java.use("javax.crypto.Mac");
        Mac.doFinal.overload("[B").implementation = function (input) {
            var result = this.doFinal(input);
            console.log("[crypto] HMAC " + this.getAlgorithm() +
                        " input (" + input.length + " bytes): " + bytesToHex(input));
            console.log("[crypto]   mac result: " + bytesToHex(result));
            return result;
        };
    });
}

// --- Native (OpenSSL) hooks for non-Java crypto ---
var EVP_EncryptUpdate = Module.findExportByName("libcrypto.so", "EVP_EncryptUpdate")
                     || Module.findExportByName("libcrypto.dylib", "EVP_EncryptUpdate");
if (EVP_EncryptUpdate) {
    Interceptor.attach(EVP_EncryptUpdate, {
        onEnter: function (args) {
            console.log("[crypto] EVP_EncryptUpdate called");
            var inLen = args[3].toInt32();
            console.log("[crypto]   input length=" + inLen);
            if (inLen > 0 && inLen <= 256) {
                console.log("[crypto]   input: " + hexdump(args[2], { length: inLen }));
            }
        }
    });
}

function bytesToHex(bytes) {
    var hex = [];
    for (var i = 0; i < bytes.length; i++) {
        hex.push(("0" + (bytes[i] & 0xFF).toString(16)).slice(-2));
    }
    return hex.join("");
}

console.log("[crypto] Crypto tracer script loaded");
""",
    "network_interceptor": r"""
"use strict";

// Network Interceptor — captures HTTP/HTTPS request and response data
// Hooks OkHttp (Android), NSURLSession (iOS), and native socket APIs.

if (Java.available) {
    Java.perform(function () {
        // --- OkHttp Interceptor ---
        try {
            var OkHttpClient = Java.use("okhttp3.OkHttpClient");
            var Interceptor = Java.use("okhttp3.Interceptor");
            var Buffer = Java.use("okio.Buffer");

            var MyInterceptor = Java.registerClass({
                name: "com.frida.NetworkInterceptor",
                implements: [Interceptor],
                methods: {
                    intercept: function (chain) {
                        var request = chain.request();
                        var url = request.url().toString();
                        var method = request.method();
                        var headers = request.headers();

                        console.log("[network] --> " + method + " " + url);
                        for (var i = 0; i < headers.size(); i++) {
                            console.log("[network]   " + headers.name(i) + ": " + headers.value(i));
                        }

                        var requestBody = request.body();
                        if (requestBody) {
                            var buf = Buffer.$new();
                            requestBody.writeTo(buf);
                            var bodyStr = buf.readUtf8();
                            console.log("[network]   body: " + (bodyStr.length > 512 ? bodyStr.substring(0, 512) + "..." : bodyStr));
                        }

                        var response = chain.proceed(request);
                        console.log("[network] <-- " + response.code() + " " + url);

                        var responseBody = response.body();
                        if (responseBody) {
                            var contentType = responseBody.contentType();
                            var bodyString = responseBody.string();
                            console.log("[network]   response (" + bodyString.length + " bytes): " +
                                (bodyString.length > 512 ? bodyString.substring(0, 512) + "..." : bodyString));
                            var newBody = Java.use("okhttp3.ResponseBody").create(contentType, bodyString);
                            return response.newBuilder().body(newBody).build();
                        }
                        return response;
                    }
                }
            });

            OkHttpClient.newBuilder.implementation = function () {
                var builder = this.newBuilder();
                builder.addInterceptor(MyInterceptor.$new());
                return builder;
            };

            console.log("[network] OkHttp interceptor installed");
        } catch (e) {
            console.log("[network] OkHttp not available: " + e);
        }

        // --- HttpURLConnection ---
        var URLConnection = Java.use("java.net.HttpURLConnection");
        URLConnection.getResponseCode.implementation = function () {
            var url = this.getURL().toString();
            var method = this.getRequestMethod();
            console.log("[network] HttpURLConnection " + method + " " + url);
            return this.getResponseCode();
        };
    });
}

if (ObjC.available) {
    // --- iOS: NSURLSession dataTask ---
    var NSURLSession = ObjC.classes.NSURLSession;
    if (NSURLSession) {
        var dataTaskWithRequest = NSURLSession["- dataTaskWithRequest:completionHandler:"];
        Interceptor.attach(dataTaskWithRequest.implementation, {
            onEnter: function (args) {
                var request = ObjC.Object(args[2]);
                var url = request.URL().absoluteString().toString();
                var method = request.HTTPMethod().toString();
                console.log("[network] --> " + method + " " + url);
                var headers = request.allHTTPHeaderFields();
                if (headers) {
                    var keys = headers.allKeys();
                    for (var i = 0; i < keys.count(); i++) {
                        var key = keys.objectAtIndex_(i).toString();
                        var val = headers.objectForKey_(key).toString();
                        console.log("[network]   " + key + ": " + val);
                    }
                }
                var body = request.HTTPBody();
                if (body) {
                    var bodyStr = ObjC.classes.NSString.alloc().initWithData_encoding_(body, 4);
                    if (bodyStr) {
                        console.log("[network]   body: " + bodyStr.toString().substring(0, 512));
                    }
                }
            }
        });
        console.log("[network] NSURLSession interceptor installed");
    }
}

// --- Native: connect() to log outbound connections ---
var connect = Module.findExportByName(null, "connect");
if (connect) {
    Interceptor.attach(connect, {
        onEnter: function (args) {
            var sockfd = args[0].toInt32();
            var addrPtr = args[1];
            var family = Memory.readU16(addrPtr);
            if (family === 2) { // AF_INET
                var port = (Memory.readU8(addrPtr.add(2)) << 8) | Memory.readU8(addrPtr.add(3));
                var ip = Memory.readU8(addrPtr.add(4)) + "." +
                         Memory.readU8(addrPtr.add(5)) + "." +
                         Memory.readU8(addrPtr.add(6)) + "." +
                         Memory.readU8(addrPtr.add(7));
                console.log("[network] connect() -> " + ip + ":" + port + " (fd=" + sockfd + ")");
            }
        }
    });
}

console.log("[network] Network interceptor script loaded");
""",
    "file_access_tracer": r"""
"use strict";

// File Access Tracer — monitors file I/O operations
// Hooks native fopen/fread/fwrite/close and Java File APIs to trace
// which files are being accessed, read, written, or deleted.

var openPaths = {};

// --- Native: fopen ---
var fopenPtr = Module.findExportByName(null, "fopen");
if (fopenPtr) {
    Interceptor.attach(fopenPtr, {
        onEnter: function (args) {
            this.path = args[0].readUtf8String();
            this.mode = args[1].readUtf8String();
        },
        onLeave: function (retval) {
            if (!retval.isNull()) {
                openPaths[retval.toString()] = this.path;
                console.log("[file] fopen(" + JSON.stringify(this.path) + ", " + JSON.stringify(this.mode) + ") = " + retval);
            }
        }
    });
}

// --- Native: fread ---
var freadPtr = Module.findExportByName(null, "fread");
if (freadPtr) {
    Interceptor.attach(freadPtr, {
        onEnter: function (args) {
            this.buf = args[0];
            this.size = args[1].toInt32();
            this.count = args[2].toInt32();
            this.stream = args[3];
        },
        onLeave: function (retval) {
            var path = openPaths[this.stream.toString()] || "unknown";
            var n = retval.toInt32();
            console.log("[file] fread(" + n + " items x " + this.size + " bytes) from " + JSON.stringify(path));
            if (n > 0 && n * this.size <= 128) {
                console.log("[file]   data: " + hexdump(this.buf, { length: n * this.size }));
            }
        }
    });
}

// --- Native: fwrite ---
var fwritePtr = Module.findExportByName(null, "fwrite");
if (fwritePtr) {
    Interceptor.attach(fwritePtr, {
        onEnter: function (args) {
            this.buf = args[0];
            this.size = args[1].toInt32();
            this.count = args[2].toInt32();
            this.stream = args[3];
            var path = openPaths[this.stream.toString()] || "unknown";
            console.log("[file] fwrite(" + this.count + " items x " + this.size + " bytes) to " + JSON.stringify(path));
            if (this.count * this.size <= 128) {
                console.log("[file]   data: " + hexdump(this.buf, { length: this.count * this.size }));
            }
        }
    });
}

// --- Native: fclose ---
var fclosePtr = Module.findExportByName(null, "fclose");
if (fclosePtr) {
    Interceptor.attach(fclosePtr, {
        onEnter: function (args) {
            var path = openPaths[args[0].toString()];
            if (path) {
                console.log("[file] fclose(" + JSON.stringify(path) + ")");
                delete openPaths[args[0].toString()];
            }
        }
    });
}

// --- Native: unlink (file deletion) ---
var unlinkPtr = Module.findExportByName(null, "unlink");
if (unlinkPtr) {
    Interceptor.attach(unlinkPtr, {
        onEnter: function (args) {
            console.log("[file] unlink(" + JSON.stringify(args[0].readUtf8String()) + ")");
        }
    });
}

// --- Java File API hooks ---
if (Java.available) {
    Java.perform(function () {
        var File = Java.use("java.io.File");

        File.$init.overload("java.lang.String").implementation = function (path) {
            console.log("[file] new File(" + JSON.stringify(path) + ")");
            return this.$init(path);
        };

        var FIS = Java.use("java.io.FileInputStream");
        FIS.$init.overload("java.lang.String").implementation = function (path) {
            console.log("[file] FileInputStream open: " + JSON.stringify(path));
            return this.$init(path);
        };

        var FOS = Java.use("java.io.FileOutputStream");
        FOS.$init.overload("java.lang.String").implementation = function (path) {
            console.log("[file] FileOutputStream open: " + JSON.stringify(path));
            return this.$init(path);
        };

        File.delete.implementation = function () {
            var path = this.getAbsolutePath();
            console.log("[file] File.delete: " + JSON.stringify(path));
            return this.delete();
        };

        File.renameTo.implementation = function (dest) {
            var src = this.getAbsolutePath();
            var dst = dest.getAbsolutePath();
            console.log("[file] File.renameTo: " + JSON.stringify(src) + " -> " + JSON.stringify(dst));
            return this.renameTo(dest);
        };
    });
}

console.log("[file] File access tracer script loaded");
""",
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FridaProcess:
    """Represents a running process discovered by Frida.

    Attributes
    ----------
    pid:
        Operating-system process identifier.
    name:
        Human-readable process name.
    user:
        User that owns the process (when available).
    is_system:
        *True* if this is a critical system process that should not be
        attached to.
    """

    pid: int
    name: str
    user: str
    is_system: bool


@dataclass
class FridaMessage:
    """A single message emitted by an injected Frida script.

    Attributes
    ----------
    timestamp:
        Unix epoch time when the message was received.
    level:
        Severity level — one of ``"info"``, ``"warning"``, ``"error"``.
    payload:
        The text content of the message.
    script_type:
        Which script template produced this message (e.g. ``"crypto_tracer"``).
    """

    timestamp: float
    level: str  # info | warning | error
    payload: str
    script_type: str


@dataclass
class FridaSession:
    """Tracks an active Frida instrumentation session.

    Attributes
    ----------
    session_id:
        Unique identifier for this session.
    target:
        PID or package name the session is attached to.
    target_type:
        ``"pid"`` when *target* is a numeric PID, ``"package"`` otherwise.
    status:
        Current status — ``"attached"``, ``"detached"``, or ``"error"``.
    start_time:
        Unix epoch time when the session was created.
    messages:
        Ordered list of messages received from the injected script.
    script_type:
        Template name or ``"custom"`` / ``"ghidra_generated"``.
    """

    session_id: str
    target: str
    target_type: str  # pid | package
    status: str  # attached | detached | error
    start_time: float
    messages: List[FridaMessage] = field(default_factory=list)
    script_type: str = "custom"


# ---------------------------------------------------------------------------
# FridaTool
# ---------------------------------------------------------------------------


class FridaTool:
    """High-level Python interface to Frida for dynamic instrumentation.

    Wraps *frida-python* to provide process enumeration, session
    management, and built-in hook templates for common reverse-engineering
    tasks such as SSL pinning bypass and crypto tracing.

    Example
    -------
    >>> tool = FridaTool()
    >>> procs = tool.list_processes()
    >>> session = tool.attach("com.example.app", script_type="ssl_pinning_bypass")
    >>> msgs = tool.get_messages(session.session_id)
    >>> tool.detach(session.session_id)
    """

    def __init__(self) -> None:
        """Initialise the tool and check for frida availability.

        Both the ``frida`` Python package and the ``frida`` CLI binary
        are checked; the tool can still function in a limited capacity
        with only the Python package.
        """
        self._python_available = FRIDA_PYTHON_AVAILABLE
        self._binary_available = shutil.which("frida") is not None

        self._sessions: Dict[str, Dict[str, Any]] = {}

        if self._python_available:
            logger.info("frida-python is available (version %s)", frida.__version__)
        else:
            logger.warning("frida-python not installed — pip install frida-tools")

        if self._binary_available:
            logger.info("frida CLI binary found on PATH")
        else:
            logger.warning("frida CLI binary not found on PATH")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether frida-python is importable.

        Returns
        -------
        bool
            *True* if ``import frida`` succeeded at module load time.
        """
        return self._python_available

    def list_processes(self) -> List[FridaProcess]:
        """Enumerate running processes on the first available device.

        Uses ``frida.get_device_manager().enumerate_devices()`` to locate
        a device, then ``device.enumerate_processes()`` to list processes.

        Returns
        -------
        list[FridaProcess]
            Sorted list of running processes.  System processes are
            flagged with ``is_system=True``.

        Raises
        ------
        RuntimeError
            If frida-python is not available or no device can be found.
        """
        if not self._python_available:
            raise RuntimeError("frida-python is not available — install with: pip install frida-tools")

        device = self._get_device()
        try:
            raw_procs = device.enumerate_processes()
        except Exception as exc:
            logger.error("Failed to enumerate processes: %s", exc)
            raise RuntimeError(f"Failed to enumerate processes: {exc}") from exc

        processes: List[FridaProcess] = []
        for p in raw_procs:
            name_lower = p.name.lower() if p.name else ""
            is_system = name_lower in SYSTEM_PROCESSES_BLOCKED
            processes.append(
                FridaProcess(
                    pid=p.pid,
                    name=p.name,
                    user="",  # frida-python does not expose user by default
                    is_system=is_system,
                )
            )

        processes.sort(key=lambda proc: (proc.is_system, proc.name.lower()))
        return processes

    def attach(
        self,
        target: str,
        script: Optional[str] = None,
        script_type: str = "custom",
        workspace_id: Optional[str] = None,
        timeout: int = DEFAULT_SCRIPT_TIMEOUT,
    ) -> FridaSession:
        """Attach to a process and inject a Frida script.

        Parameters
        ----------
        target:
            Numeric PID (as string) or package name / bundle identifier
            to attach to.
        script:
            Custom JavaScript source code.  Ignored when *script_type* is
            a built-in template name.
        script_type:
            One of the keys in :data:`SCRIPT_TEMPLATES` or ``"custom"``.
        workspace_id:
            Optional logical grouping identifier for the session.
        timeout:
            Maximum seconds the script may run before being unloaded.
            Capped at :data:`MAX_SCRIPT_TIMEOUT`.

        Returns
        -------
        FridaSession
            Metadata about the new instrumentation session.

        Raises
        ------
        ValueError
            If the target is a blocked system process or the script is
            empty.
        RuntimeError
            If frida-python is not available or attachment fails.
        """
        self._validate_target(target)

        if not self._python_available:
            raise RuntimeError("frida-python is not available")

        timeout = min(timeout, MAX_SCRIPT_TIMEOUT)

        # Resolve the JavaScript source
        js_source = self._create_script(script_type, script, None)

        # Determine target type
        target_type = "pid" if target.isdigit() else "package"

        session_id = uuid.uuid4().hex[:16]
        start = time.time()

        frida_session_obj: Any = None
        frida_script_obj: Any = None

        try:
            device = self._get_device()

            if target_type == "pid":
                pid = int(target)
                frida_session_obj = device.attach(pid)
            else:
                # Spawn the app so we can instrument before main()
                pid = device.spawn([target])
                frida_session_obj = device.attach(pid)
                device.resume(pid)

            # Create and load the script
            frida_script_obj = frida_session_obj.create_script(js_source)

            messages_list: List[FridaMessage] = []

            def _on_message(message: Dict[str, Any], data: Any) -> None:
                """Callback invoked when the injected script sends a message."""
                if message.get("type") == "send":
                    payload = message.get("payload", "")
                    msg = FridaMessage(
                        timestamp=time.time(),
                        level="info",
                        payload=str(payload),
                        script_type=script_type,
                    )
                    messages_list.append(msg)
                elif message.get("type") == "error":
                    desc = message.get("description", "unknown error")
                    stack = message.get("stack", "")
                    msg = FridaMessage(
                        timestamp=time.time(),
                        level="error",
                        payload=f"{desc}\n{stack}",
                        script_type=script_type,
                    )
                    messages_list.append(msg)
                    logger.error("Frida script error: %s", desc)

            frida_script_obj.on("message", _on_message)
            frida_script_obj.load()

            session = FridaSession(
                session_id=session_id,
                target=target,
                target_type=target_type,
                status="attached",
                start_time=start,
                messages=messages_list,
                script_type=script_type,
            )

            # Store internal references for cleanup
            self._sessions[session_id] = {
                "session": session,
                "frida_session": frida_session_obj,
                "frida_script": frida_script_obj,
                "timeout": timeout,
                "workspace_id": workspace_id,
            }

            logger.info(
                "Attached to %s (session=%s, type=%s, script=%s)",
                target, session_id, target_type, script_type,
            )
            return session

        except Exception as exc:
            # Clean up on failure
            if frida_script_obj is not None:
                try:
                    frida_script_obj.unload()
                except Exception:
                    pass
            if frida_session_obj is not None:
                try:
                    frida_session_obj.detach()
                except Exception:
                    pass

            error_session = FridaSession(
                session_id=session_id,
                target=target,
                target_type=target_type,
                status="error",
                start_time=start,
                script_type=script_type,
            )
            logger.error("Failed to attach to %s: %s", target, exc)
            raise RuntimeError(f"Failed to attach to '{target}': {exc}") from exc

    def detach(self, session_id: str) -> bool:
        """Detach from a process and unload the injected script.

        Parameters
        ----------
        session_id:
            The identifier returned by :meth:`attach`.

        Returns
        -------
        bool
            *True* if the session was successfully detached.
        """
        entry = self._sessions.pop(session_id, None)
        if entry is None:
            logger.warning("Session %s not found for detach", session_id)
            return False

        entry["session"].status = "detached"

        try:
            entry["frida_script"].unload()
        except Exception as exc:
            logger.warning("Error unloading script for session %s: %s", session_id, exc)

        try:
            entry["frida_session"].detach()
        except Exception as exc:
            logger.warning("Error detaching session %s: %s", session_id, exc)

        logger.info("Detached session %s", session_id)
        return True

    def get_session(self, session_id: str) -> Optional[FridaSession]:
        """Retrieve an active session by its identifier.

        Parameters
        ----------
        session_id:
            The session identifier returned by :meth:`attach`.

        Returns
        -------
        FridaSession or None
            The session object if it is still active, otherwise *None*.
        """
        entry = self._sessions.get(session_id)
        if entry is None:
            return None
        return entry["session"]

    def generate_script(self, ghidra_functions: List[Dict[str, Any]]) -> str:
        """Generate a Frida hook script from Ghidra analysis results.

        Takes a list of function descriptors (each with ``"name"`` and
        ``"address"`` keys) and produces JavaScript that hooks every
        function, logging entry, arguments, and return value.

        Parameters
        ----------
        ghidra_functions:
            List of dicts, each containing at least ``"name"`` and
            ``"address"`` keys.

        Returns
        -------
        str
            A complete Frida JavaScript source string.
        """
        if not ghidra_functions:
            return '"use strict";\nconsole.log("[ghidra-hooks] No functions to hook");\n'

        lines = [
            '"use strict";',
            "",
            "// Auto-generated Frida hooks from Ghidra analysis",
            "// Functions: " + str(len(ghidra_functions)),
            "",
        ]

        for func in ghidra_functions:
            name = func.get("name", "unknown")
            address = func.get("address", "0x0")
            # Ensure address is a hex string
            if isinstance(address, int):
                address = hex(address)
            if not address.startswith("0x") and not address.startswith("0X"):
                address = "0x" + str(address)

            safe_name = name.replace(" ", "_").replace(".", "_").replace("(", "").replace(")", "")
            lines.append(f"// Hook: {name} @ {address}")
            lines.append(f"var hook_{safe_name} = Module.findBaseAddress('target');")
            lines.append(f"Interceptor.attach(ptr('{address}'), {{")
            lines.append(f"    onEnter: function (args) {{")
            lines.append(f'        console.log("[ghidra-hooks] {name} called");')
            lines.append(f'        console.log("[ghidra-hooks]   arg0=" + args[0]);')
            lines.append(f'        console.log("[ghidra-hooks]   arg1=" + args[1]);')
            lines.append(f'        console.log("[ghidra-hooks]   arg2=" + args[2]);')
            lines.append(f'        console.log("[ghidra-hooks]   arg3=" + args[3]);')
            lines.append(f"        this._arg0 = args[0];")
            lines.append(f"    }},")
            lines.append(f"    onLeave: function (retval) {{")
            lines.append(f'        console.log("[ghidra-hooks] {name} returning: " + retval);')
            lines.append(f"    }}")
            lines.append(f"}});")
            lines.append("")

        lines.append('console.log("[ghidra-hooks] All ' + str(len(ghidra_functions)) + ' hooks installed");')

        return "\n".join(lines)

    def get_messages(self, session_id: str, since: int = 0) -> List[FridaMessage]:
        """Retrieve messages from an active session.

        Parameters
        ----------
        session_id:
            The session identifier.
        since:
            Index from which to start returning messages.  ``0`` returns
            all messages accumulated so far.

        Returns
        -------
        list[FridaMessage]
            Messages received since the given index.

        Raises
        ------
        KeyError
            If the session does not exist.
        """
        entry = self._sessions.get(session_id)
        if entry is None:
            raise KeyError(f"Session '{session_id}' not found")
        return entry["session"].messages[since:]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_target(self, target: str) -> None:
        """Ensure the target is not a blocked system process.

        Parameters
        ----------
        target:
            PID string or process / package name.

        Raises
        ------
        ValueError
            If the target matches a name in :data:`SYSTEM_PROCESSES_BLOCKED`.
        """
        target_lower = target.lower().strip()
        if target_lower in SYSTEM_PROCESSES_BLOCKED:
            raise ValueError(
                f"Refusing to attach to system process '{target}' — "
                "attaching could destabilise the system"
            )
        # Also check if target is a PID that might resolve to a system process
        if target.isdigit():
            try:
                procs = self.list_processes()
                pid = int(target)
                for proc in procs:
                    if proc.pid == pid and proc.is_system:
                        raise ValueError(
                            f"PID {pid} maps to system process '{proc.name}' — "
                            "refusing to attach"
                        )
            except RuntimeError:
                # frida-python may not be available; skip PID resolution
                logger.debug("Cannot validate PID against process list; skipping")

    def _create_script(
        self,
        script_type: str,
        custom_script: Optional[str],
        ghidra_functions: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Resolve the JavaScript source for a given script type.

        Parameters
        ----------
        script_type:
            Key in :data:`SCRIPT_TEMPLATES`, ``"custom"``, or
            ``"ghidra_generated"``.
        custom_script:
            User-provided JavaScript source (used only when *script_type*
            is ``"custom"``).
        ghidra_functions:
            Ghidra function list (used only when *script_type* is
            ``"ghidra_generated"``).

        Returns
        -------
        str
            The resolved JavaScript source code.

        Raises
        ------
        ValueError
            If a custom script is empty or a template name is unknown.
        """
        if script_type == "custom":
            if not custom_script or not custom_script.strip():
                raise ValueError("Custom script must not be empty")
            return custom_script

        if script_type == "ghidra_generated":
            if not ghidra_functions:
                raise ValueError("ghidra_functions must be provided for ghidra_generated script type")
            return self.generate_script(ghidra_functions)

        template = SCRIPT_TEMPLATES.get(script_type)
        if template is None:
            available = ", ".join(sorted(SCRIPT_TEMPLATES.keys()))
            raise ValueError(
                f"Unknown script_type '{script_type}'. "
                f"Available templates: {available}"
            )
        return template

    def _get_device(self) -> Any:
        """Find and return the first usable Frida device.

        Prefers a USB device, falls back to the local device.

        Returns
        -------
        frida.core.Device
            A Frida device instance.

        Raises
        ------
        RuntimeError
            If no suitable device can be found.
        """
        try:
            device_manager = frida.get_device_manager()
            devices = device_manager.enumerate_devices()

            # Prefer USB device
            for dev in devices:
                if dev.type == "usb":
                    logger.info("Using USB device: %s", dev.name)
                    return dev

            # Fall back to local
            for dev in devices:
                if dev.type == "local":
                    logger.info("Using local device: %s", dev.name)
                    return dev

            # Last resort: any non-remote device
            for dev in devices:
                if dev.type != "remote":
                    return dev

            raise RuntimeError("No usable Frida device found")
        except AttributeError:
            # Older frida versions
            return frida.get_local_device()
