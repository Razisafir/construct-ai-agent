---
name: brand-name-forge
description: Generates brand names, checks domain availability, and validates against trademark conflicts
category: design
version: 1.0.0
author: Construct
---

# Brand Name Forge

## Overview

The **Brand Name Forge** skill generates creative, memorable, and legally viable brand names for products, companies, features, or open-source projects. It checks domain name availability across TLDs, screens for trademark conflicts in major jurisdictions, evaluates linguistic meaning and cultural sensitivity across languages, and assesses SEO viability. This skill ensures that chosen names are distinctive, available, and free from negative connotations or legal risks.

## Checks Performed

- **Linguistic Meaning**: Validates that the name has no unintended meanings in major languages (English, Spanish, French, German, Mandarin, Japanese, Arabic, Hindi)
- **Cultural Sensitivity**: Screens for offensive, inappropriate, or culturally taboo terms across global regions
- **Trademark Conflicts**: Searches USPTO (US), EUIPO (EU), WIPO (global), and national trademark databases for conflicts
- **Domain Availability**: Checks `.com`, `.io`, `.co`, `.ai`, `.dev`, `.app`, `.net`, `.org`, and ccTLDs
- **Social Media Handle Availability**: Verifies username availability on major platforms
- **SEO Viability**: Analyzes search competition, keyword difficulty, and brandability score
- **Phonetic Clarity**: Tests pronunciation difficulty and memorability
- **Visual Distinctiveness**: Evaluates logo-friendliness and typography considerations

## Execution Steps

1. **Define Naming Parameters**
   - Gather brand attributes: industry, target audience, personality traits (innovative, trustworthy, playful, premium)
   - Determine name style preference: coined/neologism (Kodak), descriptive (PayPal), evocative (Amazon), acronym (IBM)
   - Specify maximum character length and pronunciation constraints
   - List competitor names to avoid similarity with

2. **Generate Name Candidates**
   - Combine morpheme blending, suffix/prefix mutation, and phonetic pattern matching
   - Use domain-specific terminology and Latin/Greek roots for technical brands
   - Apply alliteration, assonance, and rhythmic patterns for memorability
   - Generate 15-25 candidates across different naming strategies

3. **Screen Linguistic Meaning**
   - Check each candidate for existing word meanings in 8+ major languages
   - Flag names with negative, vulgar, or embarrassing translations
   - Validate pronunciation is intuitive across language families
   - Eliminate candidates with homophones to undesirable words

4. **Validate Cultural Sensitivity**
   - Cross-reference against cultural taboos and religious sensitivities
   - Check for historical negative associations or political connotations
   - Validate color, number, and animal symbolism is positive in target markets
   - Flag candidates that may alienate specific demographic groups

5. **Check Trademark Databases**
   - Search USPTO TESS database for identical and phonetically similar marks
   - Query EUIPO eSearch for European trademark conflicts
   - Check WIPO Global Brand Database for international registrations
   - Assess trademark class overlap with your industry category

6. **Verify Domain Availability**
   - Query WHOIS for `.com`, `.io`, `.co`, `.ai`, `.dev`, `.app` availability
   - Check premium domain pricing and aftermarket listings (Sedo, Afternic)
   - Evaluate alternative spellings and hyphenated variants if primary is taken
   - Verify SSL certificate availability and prior domain reputation

7. **Assess SEO and Social Media Viability**
   - Analyze Google search results for name competition and keyword difficulty
   - Check Twitter/X, Instagram, LinkedIn, GitHub, and TikTok handle availability
   - Evaluate existing search volume and brand ambiguity (common word vs. unique name)
   - Score brandability on a 1-100 scale based on uniqueness and recall

8. **Deliver Final Recommendations**
   - Rank top 5 candidates with scoring breakdown across all criteria
   - Provide trademark risk assessment (green/yellow/red) for each
   - Include domain pricing and acquisition strategy if not available at standard rates
   - Output: `brand-name-report.md` with final recommendations and contingency options

## Examples

### Example 1: SaaS Product Naming

**Input:**
```yaml
brand_parameters:
  industry: developer-tools / SaaS
  audience: software engineers, DevOps teams
  personality: technical, reliable, fast, developer-friendly
  style_preference: coined/neologism
  max_length: 10 characters
  avoid: names similar to "Docker", "Kubernetes", "Terraform"
  must_have_domain: .com or .io
```

**Output:**
```markdown
## Brand Name Forge Report — Developer Tools SaaS

### Top 5 Recommended Names

| Rank | Name | Domain (.io) | Domain (.com) | Trademark Risk | SEO Score | Cultural Score |
|------|------|-------------|---------------|----------------|-----------|----------------|
| 1 | **Deployly** | Available | Premium ($2,400) | LOW (Green) | 78/100 | 98/100 |
| 2 | **Vercore** | Available | Available | LOW (Green) | 82/100 | 95/100 |
| 3 | **Kubriq** | Taken | Available | MEDIUM (Yellow) | 85/100 | 92/100 |
| 4 | **Synsible** | Available | Taken | LOW (Green) | 75/100 | 96/100 |
| 5 | **Rapidex** | Taken | Premium ($4,800) | MEDIUM (Yellow) | 71/100 | 94/100 |

### Detailed Analysis: "Deployly" (Rank #1)

**Etymology**: Deploy + -ly (adverb suffix suggesting manner/action)
**Pronunciation**: /dɪˈplɔɪli/ — dee-PLOY-lee
**Length**: 8 characters, 3 syllables
**Linguistic Check**:
- English: "deploy" = positive tech connotation
- Spanish: No negative meaning detected
- German: No conflict detected
- Mandarin: Transliteration reads as neutral/positive
- Japanese: Katakana rendering is phonetically clean

**Trademark Search Results**:
- USPTO: No identical or confusingly similar marks in Class 9/42 (software)
- EUIPO: 1 remote similarity in unrelated Class 25 (clothing) — no conflict
- Risk Level: LOW

**Domain Strategy**:
- `deployly.io` — Available at standard registration ($35/year)
- `deployly.com` — Premium listing at $2,400; recommend negotiating or using .io

**SEO Analysis**:
- Monthly search volume for "deployly": ~0 (unique coined word — no competition)
- Brandability score: 88/100 (highly unique, memorable)
- Keyword ambiguity: None (unique neologism)
```

### Example 2: Open-Source Library Naming

**Input:**
```bash
/brand-name-forge --type open-source --language python --category data-processing
```

**Output:**
```python
# Generated candidates and analysis
candidates = [
    {
        "name": "pandrix",
        "repo": "github.com/pandrix",
        "pypi": "pypi.org/project/pandrix",
        "meaning": "Pan (all-encompassing) + matrix = universal data matrix",
        "github_available": True,
        "pypi_available": True,
        "trademark_risk": "LOW",
        "install_command": "pip install pandrix",
        "import_statement": "import pandrix",
        "score": 91
    },
    {
        "name": "dataloom",
        "repo": "github.com/dataloom",
        "pypi": "pypi.org/project/dataloom",
        "meaning": "Data + loom (weaving) = weaving data together",
        "github_available": False,
        "pypi_available": True,
        "trademark_risk": "MEDIUM",
        "install_command": "pip install dataloom",
        "import_statement": "import dataloom",
        "score": 78
    },
    {
        "name": "fluxtable",
        "repo": "github.com/fluxtable",
        "pypi": "pypi.org/project/fluxtable",
        "meaning": "Flux (flow) + table = flowing data tables",
        "github_available": True,
        "pypi_available": True,
        "trademark_risk": "LOW",
        "install_command": "pip install fluxtable",
        "import_statement": "import fluxtable",
        "score": 85
    }
]
```

### Example 3: Global Brand with Cultural Screening

**Input:**
```yaml
brand_parameters:
  industry: fintech
  target_markets: [US, UK, Brazil, India, UAE, Japan]
  personality: trustworthy, modern, accessible
  budget: premium domains acceptable
```

**Output:**
```markdown
## Cultural Sensitivity Screening Results

### Rejected Candidates

| Name | Rejection Reason |
|------|-----------------|
| "Moneta" | In Japanese, similar to "moneta" (物値) implying "thing price" — cheap connotation |
| "CredoPay" | "Credo" sounds like "creudo" (ugly) in Brazilian Portuguese slang |
| "FourCash" | Number 4 is unlucky/death-associated in China and Japan; avoid |
| "Bismi" | Too close to "Bismillah" — religious term; inappropriate commercial use |

### Approved: "Trustiva"

**Cultural Analysis**:
| Market | Assessment |
|--------|-----------|
| US/UK | "Trust" + "-iva" evokes trustworthiness and positivity |
| Brazil | Phonetically clean; no negative Portuguese connotations |
| India | "-iva" ending resonates with Sanskrit-derived names (positive) |
| UAE | No religious or cultural conflicts; trustworthy connotation |
| Japan | Katakana: トラスティバ — phonetically acceptable, no negative reading |

**Final Verdict**: APPROVED for global multi-market deployment
```

## Validation Criteria

- [ ] At least 15 initial candidates are generated using varied naming strategies
- [ ] All candidates are screened for negative meanings in 8+ languages
- [ ] Cultural sensitivity check passes for all target markets
- [ ] Trademark search returns no high-risk conflicts in relevant classes
- [ ] Primary domain (.com or prioritized TLD) is available or acquisition cost is documented
- [ ] Social media handles are available on 3+ relevant platforms
- [ ] SEO analysis shows brandability score of 70+ for recommended names
- [ ] Final report includes pronunciation guide and visual distinctiveness assessment
- [ ] At least 3 viable candidates are presented with ranked scoring

## Best Practices

- Prioritize **coined/neologism names** for SaaS and tech products — they are the most defensible trademarks
- Always check the **Urban Dictionary** and regional slang databases in addition to formal dictionaries
- Verify the name does not contain **unintentional acronyms** with negative meanings
- Test the name with native speakers from target markets before finalizing
- Secure the domain and primary social media handles **immediately** after selecting a name
- Register trademarks in **all jurisdictions** where you plan to operate within 6 months
- Avoid names that are common dictionary words — they are harder to trademark and rank for in SEO
- Consider the **verbal domain test**: if someone hears the name, can they spell it and find the website?
- Ensure the name works well as a **command-line tool** or **import statement** for developer tools
- Document the naming rationale for future brand storytelling and investor presentations

## Tools Required

| Tool | Purpose |
|------|---------|
| `whois` | Domain availability and registration data |
| `nslookup` / `dig` | DNS resolution and domain status verification |
| `curl` + trademark APIs | USPTO, EUIPO, WIPO database queries |
| `translate-shell` | Multi-language meaning verification |
| Google Keyword Planner / Ahrefs / SEMrush | SEO viability analysis |
| Namechk API / manual check | Social media handle availability |
| `sed` / `awk` | Name generation via morpheme combination |
| Urban Dictionary API / Wiktionary | Slang and informal meaning screening |

## Related Skills

- `market-research-brief` — Market validation for chosen brand direction
- `competitor-analysis` — Competitive landscape informing brand positioning
- `legal-risk-assessment` — Deep legal validation for trademark registration
