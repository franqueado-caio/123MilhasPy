#!/bin/bash
# test_api.sh - Script para testar a API

BASE_URL="http://localhost:5000"

echo "🚀 Testando API 123Milhas..."

# 1. Iniciar Tracking
echo -e "\n1️⃣ Iniciando tracking..."
TRACKING_RESP=$(curl -s -X POST $BASE_URL/api/tracking/init \
  -H "Content-Type: application/json" \
  -d '{"campanha_id":"teste","pagina_entrada":"/transferir"}')
echo $TRACKING_RESP | jq '.'

TRACKING_ID=$(echo $TRACKING_RESP | jq -r '.tracking_id')
SESSION_ID=$(echo $TRACKING_RESP | jq -r '.session_id')

# 2. Atualizar Dados Usuário
echo -e "\n2️⃣ Atualizando dados do usuário..."
curl -s -X POST $BASE_URL/api/tracking/update_user \
  -H "Content-Type: application/json" \
  -d "{\"tracking_id\":\"$TRACKING_ID\",\"nome\":\"EDNA MARIA ALVES DA SILVA\",\"cpf\":\"03752684234\",\"email\":\"edna@email.com\"}" \
  | jq '.'

# 3. Registrar Transferência
echo -e "\n3️⃣ Registrando transferência..."
curl -s -X POST $BASE_URL/api/transfer/tentativa \
  -H "Content-Type: application/json" \
  -d "{
    \"tracking_id\":\"$TRACKING_ID\",
    \"transferencia\":{
      \"banco_codigo\":\"001\",
      \"banco_nome\":\"Banco do Brasil\",
      \"agencia\":\"1234\",
      \"conta\":\"56789-0\",
      \"valor\":10782.48,
      \"valor_original_total\":43129.95,
      \"numero_cota\":1
    },
    \"usuario\":{
      \"nome\":\"EDNA MARIA ALVES DA SILVA\",
      \"cpf\":\"03752684234\",
      \"email\":\"edna@email.com\"
    }
  }" | jq '.'

# 4. Consultar Transferências
echo -e "\n4️⃣ Consultando transferências..."
curl -s -X GET "$BASE_URL/api/transfer/consultar/03752684234" | jq '.'

# 5. Verificar no banco
echo -e "\n5️⃣ Verificando no banco de dados..."
sqlite3 123milhas.db "SELECT transferencia_id, banco_nome, valor, status FROM transferencias_registro ORDER BY id DESC LIMIT 3;"

echo -e "\n✅ Teste concluído!"
