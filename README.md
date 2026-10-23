APP_NAME=AI Identity Access Gateway
APP_ENV=development
DEBUG=true

DATABASE_URL=sqlite:///./gateway.db

ADMIN_API_KEY=

HUGGINGFACE_API_KEY=
HUGGINGFACE_MODEL=meta-llama/Llama-3.1-8B-Instruct



GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.8-flash
#GEMINI_MODEL=gemini-4-argon
JWT_ISSUER=http://localhost:8000
JWT_AUDIENCE=ai-gateway
JWT_JWKS_URL=http://localhost:8000/.well-known/jwks.json

SESSION_TTL_MINUTES=60

# Azure OpenAI details  

# Azure OpenAI
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=https://openai-cyber-gpt4o.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o