"""
Copie este arquivo para secrets.py e preencha os valores reais.

    copy setup\\secrets.example.py setup\\secrets.py

Nunca versionar secrets.py (ele está no .gitignore).
Em produção, use uma senha forte e um SECRET_KEY único.
"""

# Django
SECRET_KEY = "troque-por-um-secret-key-longo-e-aleatorio"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# PostgreSQL (Docker local de exemplo)
DATABASE = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "rebel_tech_db",
    "USER": "rebeladmin",
    "PASSWORD": "secret",
    "HOST": "127.0.0.1",
    "PORT": "5432",
}
