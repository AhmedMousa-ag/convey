FROM rust:1.92.0-alpine AS builder


RUN addgroup -S convey_server && adduser -S convey_server -G convey_server

WORKDIR /home/convey_server/app
RUN chown -R convey_server:convey_server /home/convey_server/
COPY . .
RUN chown -R convey_server:convey_server .

RUN cargo clean
RUN cargo build --release --target-dir convey_server

FROM alpine
RUN addgroup -S convey_server && adduser -S convey_server -G convey_server

WORKDIR /home/convey_server/app/
COPY --from=builder /home/convey_server/app/convey_server/release/convey-server .
RUN chown -R convey_server:convey_server /home/convey_server/app/
RUN chmod +x convey-server

USER convey_server
EXPOSE 8000
CMD ["/home/convey_server/app/convey-server"]