# AgentCore Runtime image (arm64). Build from the repository root:
#   docker buildx build --platform linux/arm64 -f runtime/Dockerfile .
# No credentials are baked in; the runtime execution role supplies them.
FROM public.ecr.aws/docker/library/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
WORKDIR /app

COPY runtime/requirements.txt runtime/requirements.txt
RUN pip install --no-cache-dir -r runtime/requirements.txt

# The guide package carries the Instruction_Files, Skill_Files, and schemas.
COPY guide/ guide/
COPY runtime/ runtime/
COPY config.yaml config.yaml

RUN useradd --create-home appuser
USER appuser

EXPOSE 8080
CMD ["opentelemetry-instrument", "python", "-m", "runtime.app"]
