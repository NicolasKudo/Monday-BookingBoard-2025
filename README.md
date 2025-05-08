Cuidado APP Docker en AWS con M1/…. al crear la imagen luego de clonar el repository de github en la compu local se tiene que hacer asi:

docker buildx create --use
docker buildx build --platform linux/amd64 -t monday-bookingboard-app . --load

especificamndo que sea linux/amd64 sino no funciona

y despues push con

docker tag monday-bookingboard-app:latest 352724981691.dkr.ecr.us-east-1.amazonaws.com/monday-bookingboard-app:latest
docker push 352724981691.dkr.ecr.us-east-1.amazonaws.com/monday-bookingboard-app:latest
