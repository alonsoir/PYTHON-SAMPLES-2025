echo "Running docker compose down"
docker compose down
echo "Running COMPOSE_BAKE=true docker compose up --build -d"
COMPOSE_BAKE=true docker compose up --build -d