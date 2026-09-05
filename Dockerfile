FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY examples ./examples
RUN pip install --no-cache-dir .
ENTRYPOINT ["jurytrace"]
CMD ["demo", "--output", "/output"]
