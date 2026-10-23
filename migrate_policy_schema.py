from sqlalchemy import inspect, text

from app import models  # Register all models with Base metadata
from app.database import Base, SessionLocal, engine


def migrate():
    # Create new tables without deleting existing data.
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    team_columns = {
        column["name"]
        for column in inspector.get_columns("teams")
    }

    # Add the organization column to an existing SQLite database.
    if "organization_id" not in team_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE teams "
                    "ADD COLUMN organization_id INTEGER "
                    "REFERENCES organizations(id)"
                )
            )

        print("Added teams.organization_id")

    # Assign legacy teams to a default organization.
    with SessionLocal() as db:
        default_org = (
            db.query(models.Organization)
            .filter(
                models.Organization.slug == "default"
            )
            .first()
        )

        if default_org is None:
            default_org = models.Organization(
                name="Default Organization",
                slug="default",
                is_active=True,
            )

            db.add(default_org)
            db.commit()
            db.refresh(default_org)

            print("Created Default Organization")

        result = db.execute(
            text(
                "UPDATE teams "
                "SET organization_id = :org_id "
                "WHERE organization_id IS NULL"
            ),
            {"org_id": default_org.id},
        )

        db.commit()

        print(
            f"Assigned {result.rowcount} existing team(s) "
            "to Default Organization"
        )

    print("Policy schema migration completed.")


if __name__ == "__main__":
    migrate()