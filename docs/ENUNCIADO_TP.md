# TP: Mineração de Repositórios de Software

## Descrição

Desenvolver uma ferramenta de linha de comando que identifique problemas de manutenção de software por meio da mineração de repositórios

## Decisões Importantes

- Definição do problema

- Tecnologias utilizadas

- Origem dos dados: Git ou GitHub?

- Artefatos analisados: código, commits, issues, pull requests, branches, CI/CD etc.

- Apresentação dos resultados: métricas, visualizações, etc.

## Tools

### Git

- pydriller: Python Framework to analyse Git repositories (https://github.com/ishepard/pydriller)
- GitPython: Python library used to interact with Git repositories (https://github.com/gitpython-developers/GitPython)
- JGit: Java implementation of Git (https://github.com/eclipse-jgit/jgit)

### GitHub

- PyGithub: Typed interactions with the GitHub API (https://github.com/PyGithub/PyGithub)
- GitHub API: https://docs.github.com/en/rest: 
- GitHub Search tool (GHS): https://seart-ghs.si.usi.ch

### Command Line Interfaces (CLIs)

- typer: https://github.com/fastapi/typer
- click: https://github.com/pallets/click
- python-fire: https://github.com/google/python-fire
- argparse: https://docs.python.org/3/library/argparse.html

### Parsers

- tree-sitter: multilanguage parsing (https://github.com/tree-sitter/tree-sitter)
- python ast: Python parsing (https://docs.python.org/3/library/ast.html)
- javaparser: Java parsing (https://github.com/javaparser/javaparser)
- spoon: Java parsing (https://github.com/INRIA/spoon)
- babel parser: JavaScript parsing (https://babeljs.io/docs/babel-parser)

### Git history

- GitEvo: Code evolution analysis for Git repositories (https://github.com/andrehora/gitevo)
- CodeShovel: Git history navigation for dedicated methods (https://github.com/ataraxie/codeshovel)
- APIDiff: Detection of API breaking changes in Java (https://github.com/aserg-ufmg/apidiff)
- RefactoringMiner: Detection of refactorings in Java (https://github.com/tsantalis/RefactoringMiner)

### Metrics

- lizard: Code complexity analyser (https://github.com/terryyin/lizard)
- cloc: Line counter (https://github.com/AlDanial/cloc)
- radon: Various code metrics for Python code (https://github.com/rubik/radon)

### Code quality

- pmd: An extensible multilanguage static code analyzer (https://github.com/pmd/pmd)
- flake8: Python code quality (https://github.com/PyCQA/flake8)

### Secutiry

 - bandit: Find common security issues in Python code (https://github.com/PyCQA/bandit)

### More mining tools

- awesome-msr: https://github.com/dspinellis/awesome-msr
