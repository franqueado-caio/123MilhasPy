# app.py - Arquivo principal simples
from app import create_app

app = create_app()

if __name__ == "__main__":
    print("🚀 Servidor 123Milhas iniciado!")
    print("   - Rotas administrativas: /api/admin/estatisticas")
    print("   - Buscar: /api/admin/buscar?cpf=123")
    app.run(host="0.0.0.0", port=5000, debug=True)
