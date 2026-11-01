"""Provision only a dedicated synthetic development PostgreSQL cluster."""

import asyncio
import os

from platform_core.database import connect, migrate


async def main() -> None:
    admin = os.environ["LAB_ADMIN_DSN"]
    connection = await connect(admin)
    try:
        # Fixed identifiers: never interpolate user-controlled database/role names.
        for role in ["agent_lab_writer", "agent_lab_reader", "agent_lab_app"]:
            if not await connection.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=$1)", role
            ):
                statement = await connection.fetchval(
                    "SELECT format('CREATE ROLE %I LOGIN PASSWORD %L',$1::text,$2::text)",
                    role,
                    "synthetic-only",
                )
                await connection.execute(statement)
        for db in ["agent_orchestrator", "agent_provider"]:
            if not await connection.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=$1)", db
            ):
                await connection.execute("CREATE DATABASE " + db)
    finally:
        await connection.close()
    base = admin.rsplit("/", 1)[0]
    await migrate(base + "/agent_orchestrator", "orchestrator")
    await migrate(base + "/agent_provider", "provider")
    connection = await connect(base + "/agent_orchestrator")
    try:
        await connection.execute("""
            GRANT CONNECT ON DATABASE agent_orchestrator TO agent_lab_app;
            GRANT USAGE ON SCHEMA public TO agent_lab_app;
            GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO agent_lab_app;
            GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_lab_app;
        """)
    finally:
        await connection.close()
    connection = await connect(base + "/agent_provider")
    try:
        await connection.execute("""
            REVOKE CONNECT ON DATABASE agent_provider FROM PUBLIC;
            GRANT CONNECT ON DATABASE agent_provider TO agent_lab_reader,agent_lab_writer;
            GRANT USAGE ON SCHEMA public TO agent_lab_reader,agent_lab_writer;
            GRANT SELECT ON effects TO agent_lab_reader;
            GRANT SELECT ON provider_attempts TO agent_lab_reader;
            GRANT SELECT,INSERT ON effects,provider_attempts TO agent_lab_writer;
            GRANT SELECT,INSERT,UPDATE ON crm_entities,quota_accounts,http_resources TO agent_lab_writer;
            GRANT SELECT,INSERT ON email_deliveries TO agent_lab_writer;
            GRANT SELECT ON crm_entities,quota_accounts,email_deliveries,http_resources,search_catalog TO agent_lab_reader;
            GRANT SELECT ON search_catalog TO agent_lab_writer;
            GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_lab_writer;
        """)
    finally:
        await connection.close()
    print("Synthetic databases migrated; provider reader has SELECT only.")


if __name__ == "__main__":
    asyncio.run(main())
