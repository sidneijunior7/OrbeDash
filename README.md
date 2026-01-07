# Raidan Data Collector + OpenAI Agent (Option 2 - Organized Modules)

Projeto exemplo que coleta candles via MetaTrader5 (B3 + Forex) e Yahoo Finance,
gera um CSV e envia para um Assistente OpenAI que analisa os dados e retorna um texto
que será exibido no Streamlit.

## Preparação
1. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure variáveis de ambiente:
   - `OPENAI_API_KEY` => sua chave OpenAI (se usar o SDK oficial)
   - Opcional: caminhos para executáveis MT5, ou informe via interface

3. Prepare os terminais MT5 no mesmo host (se for usá-los).

## Rodando
```bash
streamlit run app/streamlit_app.py
```

## Observações importantes
- Este projeto é um MVP/protótipo. Em produção, trate erros, timeouts e não exponha chaves.
- O MT5 precisa estar instalado localmente e com os símbolos carregados no Market Watch.
- O agente OpenAI usado deve ter habilitadas as ferramentas de arquivos (ou o cliente deve usar endpoints que suportam arquivos).
