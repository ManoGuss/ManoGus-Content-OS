# MANOGUS CONTENT OS

Foundation local: selecione MANOGUS ou MANOGUSSS, crie uma ideia, abra o projeto, adicione referências e tarefas, edite e reabra com dados persistidos.

## Iniciar

Requer Python 3.11+ e Node 20+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
./scripts/run.sh
```

Abra http://127.0.0.1:5173. Os dados ficam em `database/manogus.sqlite3`; backups manuais em `database/backups`. Execute `python -m pytest tests/test_flow.py` após instalar `pytest` e `httpx` para testes.

**Acesso local apenas:** esta fatia ainda não possui login/CSRF. Não altere o bind para interfaces externas. Ollama é detectado, mas geração por IA não está exposta na interface. Pesquisa, Analytics e Receita estão marcados como indisponíveis ou bloqueados.

## Research Intelligence

Configure uma chave da YouTube Data API no processo backend antes de iniciar:

```bash
export YOUTUBE_API_KEY='sua-chave-local'
./scripts/run.sh
```

No Windows PowerShell, use `$env:YOUTUBE_API_KEY = 'sua-chave-local'` e inicie backend/frontend em terminais separados. Abra **Radar**, selecione janela e mercado, pesquise; clique no vídeo para ver as métricas e atualizar um novo snapshot. A primeira página é uma amostra, não a totalidade do YouTube. O score de oportunidade permanece indisponível até a coleta atingir os mínimos documentados. Não publique este servidor na rede: autenticação ainda é pendente.

## Google Trends

Na aba **Trends**, exporte o gráfico de interesse como CSV no Google Trends, informe termo, mercado, janela, URL da origem e grupo de normalização, escolha o arquivo e importe. O CSV deve conter apenas uma série. O índice 0–100 só pode ser interpretado dentro da exportação; `<1` é guardado como indisponível. A API oficial alpha não é necessária para importação manual e ainda não está conectada.

## Reference Analyzer

Abra um projeto e a referência desejada. Registre mecanismos observados do título/miniatura; para anotar narrativa, salve antes um transcript que você tem autorização para usar. Cada análise vira uma nova versão. O botão Ollama usa um modelo local instalado e devolve um rascunho inferido; sem Ollama, a análise manual continua disponível. Nenhum transcript é obtido automaticamente do YouTube.

## Script Engine

No workspace do projeto, abra **Roteiro**. Defina conceito, promessa e título provisório; crie cenas com beat, objetivo, duração, narração e plano visual. **Salvar roteiro** cria uma revisão. Reordene e restaure revisões pelo histórico. A análise da versão salva mostra alertas estruturais e duração estimada. **Gerar rascunho com Ollama** requer modelo local configurado e nunca substitui versões antigas; a ausência de pesquisa e Style DNA é registrada.

## Fluxo diário mínimo

Abra Dashboard, selecione MANOGUS ou MANOGUSSS, crie uma ideia e use **Abrir como projeto**. Também é possível usar **Novo projeto** na lista de projetos. No workspace, edite Overview, adicione até três referências em References, crie o roteiro e cenas em Script e conclua tarefas no checklist. Volte a Projetos e abra novamente: os dados vêm do SQLite. Áreas futuras aparecem como COMING SOON.
