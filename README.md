# Ranking BTG — Streamlit

## Arquivos
- `app.py`: aplicativo Streamlit
- `requirements.txt`: dependências
- `data/BTG_Consolidado.xlsx`: histórico de títulos
- `data/taxas_macro.csv`: **opcional**, exportado do notebook de taxas com colunas `Data,Selic,IPCA_12m` (taxas em % ao ano; Data no formato AAAA-MM-DD)

## Executar localmente
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar
1. Criar repositório no GitHub.
2. Enviar `app.py`, `requirements.txt`, `README.md` e a pasta `data/` com o Excel.
3. Exportar `taxas_macro.csv` do notebook e enviar para `data/` quando estiver pronto.
4. Em https://share.streamlit.io, conectar GitHub, selecionar o repositório, branch `main` e arquivo `app.py`; clicar Deploy.

## Nota
O aplicativo é uma **versão inicial exploratória**. Ainda não implementa projeções mensais de curva, fluxos de caixa dos títulos, calendário completo de feriados, disponibilidade atual, tributação específica de todos os produtos, nem a metodologia final do Ranking original.
