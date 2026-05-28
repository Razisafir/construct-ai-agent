import { useState, useCallback } from "react";

/* ─── Types ─── */
interface SkillStep {
  order: number;
  action: string;
  description: string;
  tool?: string;
  parameters: Record<string, unknown>;
}

interface Skill {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  installed: boolean;
  steps: SkillStep[];
  tools_needed: string[];
  examples: string[];
}

/* ─── Colors ─── */
const BASE = "#0c0c10";
const S1 = "#12121a";
const S2 = "#1a1a24";
const S3 = "#22222e";
const ACCENT = "#6366f1";
const TEXT = "#e8e8ec";
const TEXT_MUTED = "#94949c";
const TEXT_DIM = "#6b6b73";
const TEXT_FAINT = "#4a4a52";
const BORDER = "rgba(255,255,255,0.04)";

const ff = '"Geist Mono", "JetBrains Mono", monospace';

const categories = ["ALL", "CODING", "DESIGN", "RESEARCH", "DEVOPS", "SECURITY", "TESTING", "DOCUMENTS"];

/* ─── Demo Data ─── */
const demoSkills: Skill[] = [
  { id: "1", name: "spec-driven-development", description: "Generate specs and code from high-level descriptions.", category: "coding", version: "1.2.0", installed: true, steps: [{ order: 1, action: "parse_spec", description: "Parse spec from prompt", tool: "llm", parameters: {} }, { order: 2, action: "validate_schema", description: "Validate against schema", tool: "validator", parameters: {} }, { order: 3, action: "generate_code", description: "Generate code from spec", tool: "code_writer", parameters: {} }], tools_needed: ["llm", "validator", "code_writer"], examples: ["Generate spec for auth service"] },
  { id: "2", name: "test-driven-development", description: "Write tests first, then generate implementation.", category: "testing", version: "1.0.0", installed: true, steps: [{ order: 1, action: "generate_tests", description: "Generate test cases", tool: "code_writer", parameters: {} }, { order: 2, action: "write_impl", description: "Write implementation to pass tests", tool: "code_writer", parameters: {} }, { order: 3, action: "run_tests", description: "Run and verify tests", tool: "test_runner", parameters: {} }], tools_needed: ["code_writer", "test_runner"], examples: ["TDD for user service"] },
  { id: "3", name: "security-hardening", description: "Audit and harden code against security vulnerabilities.", category: "security", version: "2.1.0", installed: true, steps: [{ order: 1, action: "scan_vulns", description: "Scan for known vulnerabilities", tool: "scanner", parameters: {} }, { order: 2, action: "apply_fixes", description: "Apply security patches", tool: "code_writer", parameters: {} }, { order: 3, action: "verify", description: "Verify hardening", tool: "scanner", parameters: {} }], tools_needed: ["scanner", "code_writer"], examples: ["Harden auth endpoints"] },
  { id: "4", name: "component-generator", description: "Generate React components from descriptions.", category: "coding", version: "3.0.1", installed: false, steps: [{ order: 1, action: "parse_prompt", description: "Parse component description", tool: "llm", parameters: {} }, { order: 2, action: "generate_tsx", description: "Generate .tsx file", tool: "code_writer", parameters: {} }], tools_needed: ["llm", "code_writer"], examples: ["Generate a data table component"] },
  { id: "5", name: "design-token-extract", description: "Extract design tokens from Figma or CSS.", category: "design", version: "1.1.0", installed: false, steps: [{ order: 1, action: "parse_input", description: "Parse Figma/CSS input", tool: "parser", parameters: {} }, { order: 2, action: "extract_tokens", description: "Extract tokens", tool: "analyzer", parameters: {} }], tools_needed: ["parser", "analyzer"], examples: ["Extract tokens from design system"] },
  { id: "6", name: "api-documentation", description: "Generate API docs from OpenAPI specs.", category: "research", version: "0.9.0", installed: false, steps: [{ order: 1, action: "parse_openapi", description: "Parse OpenAPI spec", tool: "parser", parameters: {} }, { order: 2, action: "generate_docs", description: "Generate markdown docs", tool: "doc_writer", parameters: {} }], tools_needed: ["parser", "doc_writer"], examples: ["Document REST API"] },
  { id: "7", name: "dockerfile-generator", description: "Generate optimized Dockerfiles for any stack.", category: "devops", version: "1.3.0", installed: false, steps: [{ order: 1, action: "detect_stack", description: "Detect project stack", tool: "scanner", parameters: {} }, { order: 2, action: "write_dockerfile", description: "Write Dockerfile", tool: "code_writer", parameters: {} }], tools_needed: ["scanner", "code_writer"], examples: ["Dockerize Node.js app"] },
  { id: "8", name: "dependency-audit", description: "Audit dependencies for known vulnerabilities.", category: "security", version: "1.5.0", installed: false, steps: [{ order: 1, action: "scan_deps", description: "Scan dependencies", tool: "scanner", parameters: {} }, { order: 2, action: "report", description: "Generate audit report", tool: "report_writer", parameters: {} }], tools_needed: ["scanner", "report_writer"], examples: ["Audit npm packages"] },
  { id: "9", name: "document-conversion", description: "Convert PDF, DOCX, PPTX, and 20+ formats to Markdown.", category: "documents", version: "1.0.0", installed: true, steps: [{ order: 1, action: "detect_format", description: "Detect input file format", tool: "markitdown", parameters: {} }, { order: 2, action: "convert", description: "Convert to Markdown", tool: "markitdown", parameters: {} }, { order: 3, action: "extract_structure", description: "Extract headings, tables, structure", tool: "markitdown", parameters: {} }], tools_needed: ["markitdown"], examples: ["Convert API docs PDF to Markdown"] },
  { id: "10", name: "binary-analysis", description: "Reverse engineer binaries with Ghidra for vulnerability detection.", category: "security", version: "1.0.0", installed: false, steps: [{ order: 1, action: "analyze_binary", description: "Analyze binary with Ghidra", tool: "ghidra", parameters: {} }, { order: 2, action: "find_vulns", description: "Find vulnerabilities", tool: "ghidra", parameters: {} }, { order: 3, action: "decompile", description: "Decompile suspicious functions", tool: "ghidra", parameters: {} }], tools_needed: ["ghidra"], examples: ["Analyze suspicious ELF binary"] },
];

export default function SkillMarketplace() {
  const [activeCategory, setActiveCategory] = useState("ALL");
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [githubRepo, setGithubRepo] = useState("");
  const [skills, setSkills] = useState<Skill[]>(demoSkills);
  const [installing, setInstalling] = useState<string | null>(null);

  const filteredSkills = skills.filter((s) => {
    const matchCat = activeCategory === "ALL" || s.category === activeCategory.toLowerCase();
    return matchCat;
  });

  const handleInstall = useCallback(
    (skillId: string) => {
      setInstalling(skillId);
      setTimeout(() => {
        setSkills((prev) =>
          prev.map((s) => (s.id === skillId ? { ...s, installed: true } : s))
        );
        setInstalling(null);
      }, 600);
    },
    []
  );

  const handleGithubInstall = useCallback(() => {
    if (!githubRepo.trim()) return;
    const parts = githubRepo.trim().split("/");
    const name = parts.length >= 2 ? parts[1] : githubRepo.trim();
    const newSkill: Skill = {
      id: `gh-${Date.now()}`,
      name: name.toLowerCase().replace(/\s+/g, "-"),
      description: `Community skill from ${githubRepo.trim()}.`,
      category: "coding",
      version: "0.0.0",
      installed: true,
      steps: [
        { order: 1, action: "clone_repo", description: `Clone ${githubRepo.trim()}`, tool: "shell", parameters: {} },
        { order: 2, action: "parse_skill_md", description: "Parse SKILL.md", tool: "file_reader", parameters: {} },
        { order: 3, action: "register", description: "Register with agent", tool: "skill_manager", parameters: {} },
      ],
      tools_needed: ["shell", "file_reader", "skill_manager"],
      examples: [`Use skill from ${githubRepo.trim()}`],
    };
    setSkills((prev) => [...prev, newSkill]);
    setGithubRepo("");
  }, [githubRepo]);

  const handleView = useCallback((skill: Skill) => {
    setSelectedSkill((prev) => (prev?.id === skill.id ? null : skill));
  }, []);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        fontFamily: ff,
        background: BASE,
        color: TEXT,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 12px",
          borderBottom: `1px solid ${BORDER}`,
          flexShrink: 0,
          background: S1,
        }}
      >
        <span
          style={{
            fontSize: "10px",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: TEXT_MUTED,
          }}
        >
          Skills
        </span>
        <span style={{ fontSize: "10px", color: TEXT_DIM }}>
          {skills.length} total
        </span>
      </div>

      {/* Category Tabs */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "2px",
          padding: "6px 12px",
          borderBottom: `1px solid ${BORDER}`,
          flexShrink: 0,
          background: S1,
          overflowX: "auto",
        }}
      >
        {categories.map((cat) => {
          const active = activeCategory === cat;
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              style={{
                padding: "4px 10px",
                fontSize: "10px",
                fontWeight: 500,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                fontFamily: ff,
                background: active ? S2 : "transparent",
                color: active ? TEXT : TEXT_DIM,
                border: "none",
                borderBottom: active ? `2px solid ${ACCENT}` : "2px solid transparent",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLButtonElement).style.color = TEXT_MUTED;
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLButtonElement).style.color = TEXT_DIM;
              }}
            >
              {cat}
            </button>
          );
        })}
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {/* Table Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            borderBottom: `1px solid ${BORDER}`,
            position: "sticky",
            top: 0,
            zIndex: 1,
            background: S1,
          }}
        >
          {["NAME", "CATEGORY", "VERSION", "INSTALLED", "ACTIONS"].map((h) => (
            <div
              key={h}
              style={{
                flex: h === "NAME" ? 2 : h === "ACTIONS" ? 1.5 : 1,
                padding: "6px 8px",
                fontSize: "10px",
                fontWeight: 500,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: TEXT_DIM,
                whiteSpace: "nowrap",
              }}
            >
              {h}
            </div>
          ))}
        </div>

        {/* Table Rows */}
        {filteredSkills.map((skill) => {
          const isSelected = selectedSkill?.id === skill.id;
          return (
            <div
              key={skill.id}
              onClick={() => handleView(skill)}
              style={{
                display: "flex",
                alignItems: "center",
                cursor: "pointer",
                background: isSelected ? S2 : BASE,
                borderLeft: isSelected ? `2px solid ${ACCENT}` : "2px solid transparent",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = S2;
              }}
              onMouseLeave={(e) => {
                if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = BASE;
              }}
            >
              {/* NAME */}
              <div
                style={{
                  flex: 2,
                  padding: "6px 8px",
                  fontSize: "11px",
                  color: TEXT,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {skill.name}
              </div>
              {/* CATEGORY */}
              <div style={{ flex: 1, padding: "6px 8px" }}>
                <span
                  style={{
                    fontSize: "9px",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    background: S2,
                    color: TEXT_MUTED,
                    padding: "2px 6px",
                    borderRadius: "2px",
                  }}
                >
                  {skill.category}
                </span>
              </div>
              {/* VERSION */}
              <div
                style={{
                  flex: 1,
                  padding: "6px 8px",
                  fontSize: "11px",
                  color: TEXT_MUTED,
                  fontFamily: ff,
                }}
              >
                {skill.version}
              </div>
              {/* INSTALLED */}
              <div
                style={{
                  flex: 1,
                  padding: "6px 8px",
                  fontSize: "11px",
                  color: skill.installed ? TEXT_DIM : ACCENT,
                  fontFamily: ff,
                }}
              >
                {skill.installed ? "yes" : "no"}
              </div>
              {/* ACTIONS */}
              <div
                style={{
                  flex: 1.5,
                  padding: "6px 8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleView(skill);
                  }}
                  style={{
                    padding: "3px 8px",
                    fontSize: "9px",
                    fontFamily: ff,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    background: S2,
                    color: TEXT_MUTED,
                    border: "none",
                    borderRadius: "2px",
                    cursor: "pointer",
                  }}
                >
                  VIEW
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleView(skill);
                  }}
                  style={{
                    padding: "3px 8px",
                    fontSize: "9px",
                    fontFamily: ff,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    background: S2,
                    color: TEXT_MUTED,
                    border: "none",
                    borderRadius: "2px",
                    cursor: "pointer",
                  }}
                >
                  RUN
                </button>
                {!skill.installed && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleInstall(skill.id);
                    }}
                    disabled={installing === skill.id}
                    style={{
                      padding: "3px 8px",
                      fontSize: "9px",
                      fontFamily: ff,
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      background: S2,
                      color: installing === skill.id ? TEXT_DIM : ACCENT,
                      border: "none",
                      borderRadius: "2px",
                      cursor: "pointer",
                    }}
                  >
                    {installing === skill.id ? "..." : "INST"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* GitHub Install */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "8px 12px",
          borderTop: `1px solid ${BORDER}`,
          borderBottom: `1px solid ${BORDER}`,
          flexShrink: 0,
          background: S1,
        }}
      >
        <span
          style={{
            fontSize: "10px",
            fontWeight: 500,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: TEXT_DIM,
            whiteSpace: "nowrap",
          }}
        >
          Install from GitHub
        </span>
        <input
          type="text"
          value={githubRepo}
          onChange={(e) => setGithubRepo(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleGithubInstall();
          }}
          placeholder="owner/repo"
          style={{
            flex: 1,
            padding: "4px 8px",
            fontSize: "11px",
            fontFamily: ff,
            background: BASE,
            color: TEXT,
            border: `1px solid ${BORDER}`,
            outline: "none",
          }}
        />
        <button
          onClick={handleGithubInstall}
          disabled={!githubRepo.trim()}
          style={{
            padding: "4px 10px",
            fontSize: "10px",
            fontFamily: ff,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            fontWeight: 500,
            background: S2,
            color: githubRepo.trim() ? TEXT : TEXT_DIM,
            border: "none",
            borderRadius: "2px",
            cursor: githubRepo.trim() ? "pointer" : "default",
          }}
        >
          INSTALL
        </button>
      </div>

      {/* Selected Detail Panel */}
      {selectedSkill && (
        <div
          style={{
            flexShrink: 0,
            maxHeight: "240px",
            overflow: "auto",
            background: S2,
            borderTop: `1px solid ${BORDER}`,
          }}
        >
          {/* Detail Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "6px 12px",
              borderBottom: `1px solid ${BORDER}`,
            }}
          >
            <span style={{ fontSize: "11px", fontWeight: 600, color: TEXT }}>
              {selectedSkill.name}
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                style={{
                  fontSize: "9px",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  background: S3,
                  color: TEXT_MUTED,
                  padding: "2px 6px",
                  borderRadius: "2px",
                }}
              >
                {selectedSkill.category}
              </span>
              <span style={{ fontSize: "10px", color: TEXT_DIM }}>
                v{selectedSkill.version}
              </span>
              <button
                onClick={() => setSelectedSkill(null)}
                style={{
                  fontSize: "10px",
                  color: TEXT_DIM,
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: ff,
                }}
              >
                x
              </button>
            </div>
          </div>

          {/* Description */}
          <div style={{ padding: "6px 12px", borderBottom: `1px solid ${BORDER}` }}>
            <p style={{ fontSize: "11px", color: TEXT_MUTED, margin: 0 }}>
              {selectedSkill.description}
            </p>
          </div>

          {/* Steps */}
          <div style={{ padding: "6px 12px", borderBottom: `1px solid ${BORDER}` }}>
            <div
              style={{
                fontSize: "10px",
                fontWeight: 500,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: TEXT_DIM,
                marginBottom: "6px",
              }}
            >
              Steps
            </div>
            {selectedSkill.steps.map((step) => (
              <div
                key={step.order}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "3px 0",
                  fontSize: "11px",
                  color: TEXT_MUTED,
                }}
              >
                <span
                  style={{
                    fontSize: "9px",
                    color: TEXT_FAINT,
                    fontFamily: ff,
                    minWidth: "14px",
                  }}
                >
                  {String(step.order).padStart(2, "0")}
                </span>
                <span style={{ color: TEXT, fontFamily: ff }}>{step.action}</span>
                <span style={{ color: TEXT_DIM }}>{step.description}</span>
                {step.tool && (
                  <span
                    style={{
                      fontSize: "9px",
                      background: S3,
                      color: TEXT_FAINT,
                      padding: "1px 4px",
                      borderRadius: "2px",
                    }}
                  >
                    {step.tool}
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* Tools */}
          <div style={{ padding: "6px 12px" }}>
            <div
              style={{
                fontSize: "10px",
                fontWeight: 500,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: TEXT_DIM,
                marginBottom: "6px",
              }}
            >
              Tools
            </div>
            <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
              {selectedSkill.tools_needed.map((tool) => (
                <span
                  key={tool}
                  style={{
                    fontSize: "9px",
                    background: S3,
                    color: TEXT_MUTED,
                    padding: "2px 6px",
                    borderRadius: "2px",
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                  }}
                >
                  {tool}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
