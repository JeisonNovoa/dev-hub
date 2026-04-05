from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_project_or_404
from app.models import Command
from app.schemas.project import CommandCreate, CommandResponse, CommandUpdate

router = APIRouter()


def _get_command_or_404(cmd_id: int, project_id: int, db: Session) -> Command:
    cmd = db.query(Command).filter(
        Command.id == cmd_id, Command.project_id == project_id
    ).first()
    if not cmd:
        raise HTTPException(status_code=404, detail="Comando no encontrado")
    return cmd


@router.get("", response_model=list[CommandResponse])
def list_commands(slug: str, db: Session = Depends(get_db)) -> list[Command]:
    project = get_project_or_404(slug, db)
    return project.commands


@router.post("", response_model=CommandResponse, status_code=status.HTTP_201_CREATED)
def create_command(slug: str, data: CommandCreate, db: Session = Depends(get_db)) -> Command:
    project = get_project_or_404(slug, db)
    cmd = Command(
        project_id=project.id,
        label=data.label,
        command=data.command,
        order=data.order,
        type=data.type,
    )
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    return cmd


@router.put("/{cmd_id}", response_model=CommandResponse)
def update_command(slug: str, cmd_id: int, data: CommandUpdate, db: Session = Depends(get_db)) -> Command:
    project = get_project_or_404(slug, db)
    cmd = _get_command_or_404(cmd_id, project.id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cmd, field, value)
    db.commit()
    db.refresh(cmd)
    return cmd


@router.delete("/{cmd_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_command(slug: str, cmd_id: int, db: Session = Depends(get_db)) -> None:
    project = get_project_or_404(slug, db)
    cmd = _get_command_or_404(cmd_id, project.id, db)
    db.delete(cmd)
    db.commit()
