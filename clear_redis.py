import redis


# Substitua pelos seus dados:
host = "redis-14400.c8.us-east-1-2.ec2.redns.redis-cloud.com"
port = 14400
password = "XQTQYdroga4LBjkkkXGTTJBPr4g83fR5"

# Conecta ao Redis Cloud
r = redis.Redis(
    host=host,
    port=port,
    password=password
)

# Apagar tudo do banco atual
r.flushdb()
