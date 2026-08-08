"""
Copie este arquivo para secrets.py (desenvolvimento local):

    copy setup\\secrets.example.py setup\\secrets.py

Em produção (Docker), prefira variáveis de ambiente via arquivo `.env`
(veja `.env.example`). O `settings.py` lê env primeiro e usa este arquivo
como fallback local.

Nunca versionar `setup/secrets.py` nem `.env`.
"""

# Django
SECRET_KEY = "troque-por-um-secret-key-longo-e-aleatorio"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# PostgreSQL (Docker local de exemplo)
DATABASE = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "rebel_tech_db",
    "USER": "rebeladmin",
    "PASSWORD": "secret",
    "HOST": "127.0.0.1",
    "PORT": "5432",
}
