---
name: leveltravel-migrations
description: Use when generating, applying, rolling back, or verifying Rails migrations in the LevelTravel repository. Covers the required LT CLI bootstrap, entering the Rails container, the project migration style with safety_assured and existence guards, and schema consistency checks.
---

# LevelTravel Migrations

Use this skill whenever work in this repository requires a Rails migration or any migration-related command.

This skill governs migration workflow only. Do not change application code merely because this skill loaded.

## Bootstrap LT CLI

Before any LT command on the host, load the helper:

```bash
source ./lt.sh
```

Run LT commands through the loaded function, not through raw Docker commands, unless a repository instruction explicitly requires otherwise.

For any interaction with Rails, enter the Rails container first:

```bash
lt sh
```

Run all Rails migration commands inside that shell.

## Create Migrations

Do not create migration files manually.

Generate migrations only through Rails generators inside `lt sh`:

```bash
bundle exec rails generate migration AddFooToBars foo:string
```

After generation:

- inspect the migration file for naming and intent;
- keep the change scoped to one concern;
- prefer the project pattern `t.integer :client_id, null: false, index: true` instead of foreign keys;
- add existence checks before destructive or repeatable operations.

## Project Migration Style

Use project patterns, not generic Rails defaults.

When creating tables:

- prefer explicit `up` and `down`, not `change`;
- create tables with `if_not_exists: true`;
- drop tables with `if_exists: true`;
- wrap unsafe operations in `safety_assured`.

Example:

```ruby
def up
  create_table :hotel_organizations, if_not_exists: true do |t|
    t.integer :client_id, null: false, index: true
    t.timestamps
  end
end

def down
  safety_assured { drop_table :hotel_organizations, if_exists: true }
end
```

For indexes:

- prefer `add_index_if_not_exists`;
- prefer `remove_index_if_exists` in rollback paths;
- wrap index add/remove operations in `safety_assured`.

Example:

```ruby
def up
  safety_assured do
    add_index_if_not_exists(:orders, %i[client_id created_at])
  end
end

def down
  safety_assured do
    remove_index_if_exists(:orders, %i[client_id created_at])
  end
end
```

Main rule:

- always check that the object exists before mutating or deleting it when the migration API supports that guard;
- favor idempotent migration steps so reruns and rollbacks fail less often.

## Run Migrations

Apply migrations inside `lt sh`:

```bash
bundle exec rails db:migrate
```

After running them:

- clean `db/schema.rb` from noise first, leaving only the state that should remain after the migration;
- inspect `db/schema.rb`;
- keep schema changes limited to the intended migration work;
- keep `ActiveRecord::Schema.define(version: ...)` aligned with the latest applied migration.
- refresh the test database schema with `bundle exec rails db:test:load`.

## Roll Back And Re-Run

When a rollback check is needed, run it inside `lt sh`:

```bash
bundle exec rails db:rollback STEP=1
bundle exec rails db:migrate
```

After `db:rollback`, first clean `db/schema.rb` from noise so it reflects the expected post-rollback state. Only after that continue with migration edits or the next `db:migrate`.

Use this forward-and-backward check when the change affects data shape, defaults, indexes, constraints, or anything that may fail on rollback.

If more than one step must be rolled back, state the exact command you are using and why.
