import logging
import sys


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    # uvicorn.access ya loguea cada request — silenciarlo en producción evita duplicados
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # SQLAlchemy: solo mostrar queries en debug
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if debug else logging.WARNING
    )
