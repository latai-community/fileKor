# Taxonomy Configuration

Labels are used to classify and categorize files. The taxonomy is defined in a `labels.properties` file.

## Config File Search Order

The tool searches for `labels.properties` in this order:

1. Custom path (via `--config` flag)
2. `labels.properties` in current directory
3. `.filekor/labels.properties`
4. `~/.filekor/labels.properties`
5. Built-in defaults

## Format

```properties
# Labels configuration
# Format: LABEL=synonym1,synonym2,synonym3

finance=economy,budget,cost,costs,money,financial,billing,invoice
contract=agreement,contract,terms,conditions,legal
legal=law,compliance,gdpr,privacy,policy,regulation
architecture=design,architecture,blueprint,structure
specification=spec,specs,requirement,requirements
documentation=docs,documentation,manual,guide,readme
```

## Label Structure

- **Label Name**: The main category (e.g., `finance`, `legal`)
- **Synonyms**: Alternative words that map to that label (e.g., `budget`, `cost` → `finance`)

## Using Custom Taxonomy

```bash
# With labels command
filekor labels documento.pdf -c custom-labels.properties

# With sidecar
# (uses default taxonomy automatically)
```

## Built-in Default Labels

If no `labels.properties` is found, these defaults are used:

| Label | Synonyms |
|-------|---------|
| finance | economy, budget, cost, costs, money, financial, billing, invoice |
| contract | agreement, contract, terms, conditions, legal |
| legal | law, compliance, gdpr, privacy, policy, regulation |
| architecture | design, architecture, blueprint, structure |
| specification | spec, specs, requirement, requirements |
| documentation | docs, documentation, manual, guide, readme |