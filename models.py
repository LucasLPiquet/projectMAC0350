from sqlmodel import Field, Relationship, SQLModel
from fastapi import FastAPI
from typing import List, Optional

class Amizade(SQLModel, table=True):
    usuario_id: Optional[int] = Field(default=None, foreign_key="usuario.id", primary_key=True)
    amigo_id: Optional[int] = Field(default=None, foreign_key="usuario.id", primary_key=True)

class UsuarioConquista(SQLModel, table=True):
    usuario_id: Optional[int] = Field(
        default=None,
        foreign_key="usuario.id",
        primary_key=True
    )

    conquista_id: Optional[int] = Field(
        default=None,
        foreign_key="conquista.id",
        primary_key=True
    )


class Usuario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    nome: str
    senha: str
    bio: str = "Sem bio"
    primeiro_login: bool = True
    numero_amigos: int = 0
    temp_pontuacao: int = 0
    
    pontuacao: int = 0
    amigos: List["Usuario"] = Relationship(
        link_model=Amizade,
        sa_relationship_kwargs={
            "primaryjoin": "Usuario.id==Amizade.usuario_id",
            "secondaryjoin": "Usuario.id==Amizade.amigo_id",
        },
    )

    conquistas: List["Conquista"] = Relationship(link_model=UsuarioConquista, back_populates="usuarios")


class Conquista(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    nome: str
    descricao: str

    usuarios: List["Usuario"] = Relationship(link_model=UsuarioConquista, back_populates="conquistas")

