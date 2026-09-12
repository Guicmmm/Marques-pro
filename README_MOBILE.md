# Marques Pro — celular

A interface é responsiva e pode ser aberta no Safari/Chrome.

## Modo real
O backend usa API-Football para fixtures e previsões. Não é necessário configurar odds reais de bookmaker.

## Hospedagem
Publique estes arquivos em um serviço que rode Python 3.11+ e defina a variável `API_FOOTBALL_KEY`. A aplicação escuta a porta fornecida pela variável `PORT`.

Depois de publicado, abra a URL HTTPS no celular. No Safari, use Compartilhar → Adicionar à Tela de Início para criar um atalho como app.

## Teste
O ZIP inclui a interface e o backend; para testar sem dados reais, use o arquivo de teste mobile separado.
