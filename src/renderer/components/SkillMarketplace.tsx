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
    <div className="flex flex-col h-full overflow-hidden font-mono bg-c-base text-c-text">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 shrink-0" style={{ borderBottom: "1px solid var(--c-border)", background: "var(--c-s1)" }}>
        <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--c-text2)" }}>
          Skills
        </span>
        <span className="text-[10px]" style={{ color: "var(--c-text3)" }}>
          {skills.length} total
        </span>
      </div>

      {/* Category Tabs */}
      <div className="flex items-center gap-[2px] px-3 py-1.5 shrink-0 overflow-x-auto" style={{ borderBottom: "1px solid var(--c-border)", background: "var(--c-s1)" }}>
        {categories.map((cat) => {
          const active = activeCategory === cat;
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className="px-2.5 py-1 text-[10px] font-medium uppercase tracking-wider font-mono border-none cursor-pointer whitespace-nowrap"
              style={{
                background: active ? "var(--c-s2)" : "transparent",
                color: active ? "var(--c-text)" : "var(--c-text3)",
                borderBottom: active ? "2px solid var(--c-accent)" : "2px solid transparent",
              }}
              onMouseEnter={(e) => { if (!active) (e.currentTarget as HTMLButtonElement).style.color = "var(--c-text2)"; }}
              onMouseLeave={(e) => { if (!active) (e.currentTarget as HTMLButtonElement).style.color = "var(--c-text3)"; }}
            >
              {cat}
            </button>
          );
        })}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {/* Table Header */}
        <div className="flex items-center sticky top-0 z-[1]" style={{ borderBottom: "1px solid var(--c-border)", background: "var(--c-s1)" }}>
          {["NAME", "CATEGORY", "VERSION", "INSTALLED", "ACTIONS"].map((h) => (
            <div key={h} className="px-2 py-1.5 text-[10px] font-medium uppercase tracking-wider whitespace-nowrap" style={{ flex: h === "NAME" ? 2 : h === "ACTIONS" ? 1.5 : 1, color: "var(--c-text3)" }}>
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
              className="flex items-center cursor-pointer"
              style={{
                background: isSelected ? "var(--c-s2)" : "var(--c-base)",
                borderLeft: isSelected ? "2px solid var(--c-accent)" : "2px solid transparent",
              }}
              onMouseEnter={(e) => { if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = "var(--c-s2)"; }}
              onMouseLeave={(e) => { if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = "var(--c-base)"; }}
            >
              <div className="px-2 py-1.5 text-[11px] overflow-hidden text-ellipsis whitespace-nowrap" style={{ flex: 2, color: "var(--c-text)" }}>{skill.name}</div>
              <div className="px-2 py-1.5" style={{ flex: 1 }}>
                <span className="text-[9px] uppercase tracking-wider px-1.5 py-[2px] rounded-sm" style={{ background: "var(--c-s2)", color: "var(--c-text2)" }}>{skill.category}</span>
              </div>
              <div className="px-2 py-1.5 text-[11px] font-mono" style={{ flex: 1, color: "var(--c-text2)" }}>{skill.version}</div>
              <div className="px-2 py-1.5 text-[11px] font-mono" style={{ flex: 1, color: skill.installed ? "var(--c-text3)" : "var(--c-accent)" }}>{skill.installed ? "yes" : "no"}</div>
              <div className="px-2 py-1.5 flex items-center gap-1" style={{ flex: 1.5 }}>
                <button onClick={(e) => { e.stopPropagation(); handleView(skill); }} className="px-2 py-[3px] text-[9px] font-mono uppercase tracking-wider border-none rounded-sm cursor-pointer" style={{ background: "var(--c-s2)", color: "var(--c-text2)" }}>VIEW</button>
                <button onClick={(e) => { e.stopPropagation(); handleView(skill); }} className="px-2 py-[3px] text-[9px] font-mono uppercase tracking-wider border-none rounded-sm cursor-pointer" style={{ background: "var(--c-s2)", color: "var(--c-text2)" }}>RUN</button>
                {!skill.installed && (
                  <button onClick={(e) => { e.stopPropagation(); handleInstall(skill.id); }} disabled={installing === skill.id} className="px-2 py-[3px] text-[9px] font-mono uppercase tracking-wider border-none rounded-sm cursor-pointer" style={{ background: "var(--c-s2)", color: installing === skill.id ? "var(--c-text3)" : "var(--c-accent)" }}>
                    {installing === skill.id ? "..." : "INST"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* GitHub Install */}
      <div className="flex items-center gap-2 px-3 py-2 shrink-0" style={{ borderTop: "1px solid var(--c-border)", borderBottom: "1px solid var(--c-border)", background: "var(--c-s1)" }}>
        <span className="text-[10px] font-medium uppercase tracking-wider whitespace-nowrap" style={{ color: "var(--c-text3)" }}>
          Install from GitHub
        </span>
        <input
          type="text"
          value={githubRepo}
          onChange={(e) => setGithubRepo(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleGithubInstall(); }}
          placeholder="owner/repo"
          className="flex-1 px-2 py-1 text-[11px] font-mono outline-none"
          style={{ background: "var(--c-base)", color: "var(--c-text)", border: "1px solid var(--c-border)" }}
        />
        <button
          onClick={handleGithubInstall}
          disabled={!githubRepo.trim()}
          className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider font-medium border-none rounded-sm"
          style={{ background: "var(--c-s2)", color: githubRepo.trim() ? "var(--c-text)" : "var(--c-text3)", cursor: githubRepo.trim() ? "pointer" : "default" }}
        >
          INSTALL
        </button>
      </div>

      {/* Selected Detail Panel */}
      {selectedSkill && (
        <div className="shrink-0 max-h-[240px] overflow-auto" style={{ background: "var(--c-s2)", borderTop: "1px solid var(--c-border)" }}>
          <div className="flex items-center justify-between px-3 py-1.5" style={{ borderBottom: "1px solid var(--c-border)" }}>
            <span className="text-[11px] font-semibold" style={{ color: "var(--c-text)" }}>{selectedSkill.name}</span>
            <div className="flex items-center gap-2">
              <span className="text-[9px] uppercase tracking-wider px-1.5 py-[2px] rounded-sm" style={{ background: "var(--c-s3)", color: "var(--c-text2)" }}>{selectedSkill.category}</span>
              <span className="text-[10px]" style={{ color: "var(--c-text3)" }}>v{selectedSkill.version}</span>
              <button onClick={() => setSelectedSkill(null)} className="text-[10px] bg-none border-none cursor-pointer font-mono" style={{ color: "var(--c-text3)" }}>x</button>
            </div>
          </div>
          <div className="px-3 py-1.5" style={{ borderBottom: "1px solid var(--c-border)" }}>
            <p className="text-[11px] m-0" style={{ color: "var(--c-text2)" }}>{selectedSkill.description}</p>
          </div>
          <div className="px-3 py-1.5" style={{ borderBottom: "1px solid var(--c-border)" }}>
            <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Steps</div>
            {selectedSkill.steps.map((step) => (
              <div key={step.order} className="flex items-center gap-2 py-[3px] text-[11px]" style={{ color: "var(--c-text2)" }}>
                <span className="text-[9px] font-mono min-w-[14px]" style={{ color: "var(--c-text4)" }}>{String(step.order).padStart(2, "0")}</span>
                <span className="font-mono" style={{ color: "var(--c-text)" }}>{step.action}</span>
                <span style={{ color: "var(--c-text3)" }}>{step.description}</span>
                {step.tool && <span className="text-[9px] px-1 py-[1px] rounded-sm" style={{ background: "var(--c-s3)", color: "var(--c-text4)" }}>{step.tool}</span>}
              </div>
            ))}
          </div>
          <div className="px-3 py-1.5">
            <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Tools</div>
            <div className="flex gap-1 flex-wrap">
              {selectedSkill.tools_needed.map((tool) => (
                <span key={tool} className="text-[9px] px-1.5 py-[2px] rounded-sm uppercase tracking-wider" style={{ background: "var(--c-s3)", color: "var(--c-text2)" }}>{tool}</span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
