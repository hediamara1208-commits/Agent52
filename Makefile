.PHONY: deploy seed destroy

# Extra CDK context, e.g. make deploy CDK_ARGS="-c budget_email=me@example.com -c enable_identity=true"
CDK_ARGS ?=
export CDK_ARGS

deploy:
	bash scripts/deploy.sh

seed:
	bash scripts/seed.sh

destroy:
	bash scripts/destroy.sh
