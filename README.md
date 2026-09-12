# Marques Pro v11

Versão de teste sem necessidade de odds reais. O aplicativo usa previsões/modelo e calcula odds justas estimadas para montar cupons.

## Como usar
1. Instale Python 3.10+.
2. Abra o terminal na pasta do projeto.
3. Configure `API_FOOTBALL_KEY` se quiser dados reais de partidas e previsões.
4. Execute `python server.py`.
5. Abra `http://127.0.0.1:8787`.

Sem chave de API, a interface abre normalmente, mas a análise de partidas reais não terá dados externos.

O histórico é salvo em `marques_pro_history.json`, sem depender de SQLite.

**Importante:** as probabilidades são estimativas do modelo, não garantia de resultado.
