"""Languages app models."""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from core.base import Base
from core.mixins import SlugMixin


class Language(Base):
    """Язык."""

    name_ru = Column(String(256), nullable=False)
    name_en = Column(String(256), nullable=False)
    name_local = Column(String(256), nullable=False, server_default='')
    isocode = Column(String(8), nullable=False, unique=True, index=True)
    country_ru = Column(String(256), nullable=True, server_default='')
    country_en = Column(String(256), nullable=True, server_default='')
    sorting = Column(Integer, nullable=False, server_default='0')
    learning_available = Column(Boolean, nullable=False, server_default='false')
    interface_available = Column(Boolean, nullable=False, server_default='false')
    flag_icon = Column(String(1024), nullable=True)  # path to flag icon

    # Relationships (none are declared here from Language side explicitly except images/backref)
    # Language.images relationship is created by LanguageCoverImage below via backref
    native_for = relationship(
        'User',
        back_populates='native_languages',
        secondary='languages_usernativelanguage',
        viewonly=True,
        lazy='selectin',
    )
    learning_by = relationship(
        'User',
        secondary='languages_userlearninglanguage',
        viewonly=True,
        lazy='selectin',
    )

    __table_args__ = (
        Index(
            'ix_languages_language_sorting_name_isocode',
            'sorting',
            'name_en',
            'isocode',
        ),
    )

    def __repr__(self):
        return f'<Language(name={self.name_local}, isocode={self.isocode})>'


class LanguageCoverImage(Base):
    """Картинка-обложка языка."""

    # fields
    image_url = Column(String(1024), nullable=False)  # path to image
    default = Column(Boolean, nullable=False, server_default='false')

    # FK
    language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('languages_language.id', ondelete='CASCADE'),
        nullable=False,
    )

    # Relationships (FK)
    language = relationship('Language', backref='images', lazy='selectin')

    __table_args__ = (Index('ix_languages_languagecoverimage_created', 'created'),)

    def __repr__(self):
        return f'<LanguageCoverImage(language_id={self.language_id}, default={self.default})>'


class UserLearningLanguage(Base, SlugMixin):
    """Изучаемый язык пользователя."""

    # fields
    level = Column(String(32), nullable=True, server_default='')
    is_confirmed = Column(
        Boolean,
        nullable=False,
        server_default='false',
        insert_default=False,
    )
    is_taught = Column(
        Boolean,
        nullable=False,
        server_default='false',
        default=False,
        insert_default=False,
    )

    # FK
    language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('languages_language.id', ondelete='CASCADE'),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users_user.id', ondelete='CASCADE'),
        nullable=False,
    )
    cover_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('languages_languagecoverimage.id', ondelete='SET NULL'),
        nullable=True,
    )

    # Relationships (FK)
    language = relationship('Language', backref='learning_by_detail', lazy='selectin')
    user = relationship('User', backref='learning_languages_detail', lazy='selectin')
    cover = relationship('LanguageCoverImage', backref='covers', lazy='selectin')

    __slug_source__ = ['user', 'language__isocode']

    __table_args__ = (
        UniqueConstraint(
            'language_id', 'user_id', name='unique_user_learning_language'
        ),
        Index('ix_languages_userlearninglanguage_created', 'created'),
    )

    def __repr__(self):
        return f'<UserLearningLanguage(user_id={self.user_id}, language_id={self.language_id})>'


class UserNativeLanguage(Base, SlugMixin):
    """Родной язык пользователя."""

    # FK
    language_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('languages_language.id', ondelete='CASCADE'),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users_user.id', ondelete='CASCADE'),
        nullable=False,
    )

    # Relationships (FK)
    language = relationship('Language', backref='native_for_detail', lazy='selectin')
    user = relationship('User', backref='native_languages_detail', lazy='selectin')

    __slug_source__ = ['user', 'language__isocode']

    __table_args__ = (
        UniqueConstraint('language_id', 'user_id', name='unique_user_native_language'),
        Index('ix_languages_usernativelanguage_created', 'created'),
    )

    def __repr__(self):
        return f'<UserNativeLanguage(user_id={self.user_id}, language_id={self.language_id})>'
