FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build
COPY server/pom.xml .
COPY server/src src
COPY data/administrative /data/administrative
RUN mvn -B -DskipTests package
FROM eclipse-temurin:17-jre-alpine
RUN addgroup -S weather && adduser -S weather -G weather && apk add --no-cache curl
WORKDIR /app
COPY --from=build /build/target/weather-stream-1.0.0.jar app.jar
USER weather
EXPOSE 8000 9000
ENTRYPOINT ["java", "-jar", "app.jar"]
