
# Trading Journal (Work In Progress)

A simple trading journal application (work in progress).

This repository contains the backend of a trading journal designed to help you record and analyse trades. The system is specially designed to support journaling trades for the "wheel" options strategy, but it also supports other trade types such as long/short spot positions, forex, and more.

Important: the project is still under active development. There is a backend in this repo, but the frontend UI has not been implemented yet.

## Key features

- Journal trades with rich metadata (strategy, entry/exit, P/L, notes).
- Built-in support and data model conveniences for the Wheel strategy (puts/calls lifecycle tracking).
- Flexible support for other trade types: long/short spots, forex, futures, etc.
- Backend-first design with tests and migration helpers.

## Repository layout

- `backend/` — Python backend code (API, models, services, migrations, tests).
- `backend/trading_journal/` — core application modules: CRUD, models, DTOs, services, and security.
- `backend/tests/` — unit tests targeting the backend logic and DB layer.


## License

See the `LICENSE` file in the project root for license details.


