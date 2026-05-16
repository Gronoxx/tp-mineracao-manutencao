# Como rodar

- instale as dependencias em requirements.txt (`pip install -r .\extracao\requirements.txt`)
- Adicione os repositórios e o intervalo de tempo que você quer importar em `execucao/mineracao.py`
- Execute no terminal `python -m extracao.execucao.mineracao`
- Para ver os commits com as diffs execute `python -m extracao.execucao.visualizacao`
- Para ver e poder excluir, execute `python -m extracao.execucao.filtro_smells`