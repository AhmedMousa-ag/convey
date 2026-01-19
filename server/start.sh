docker stop convey_server && docker rm convey_server

docker build -t convey_server . && docker run --name convey_server -p 3000:3000 convey_server