"""
SQLAlchemy models for the MET Museum artwork database
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime, ForeignKey,
    Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Artwork(Base):
    """
    Stores artwork data from the Metropolitan Museum of Art API
    Each record represents one artwork with its metadata
    """
    __tablename__ = 'artworks'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # MET Museum identifiers
    met_object_id = Column(Integer, unique=True, nullable=False, index=True)

    # Basic artwork information
    title = Column(String(500), nullable=False, index=True)
    object_name = Column(String(200), nullable=True)
    object_date = Column(String(200), nullable=True)
    object_begin_date = Column(Integer, nullable=True)
    object_end_date = Column(Integer, nullable=True)

    # Artist information
    artist_display_name = Column(String(300), nullable=True)
    artist_display_bio = Column(String(500), nullable=True)
    artist_nationality = Column(String(100), nullable=True)
    artist_gender = Column(String(50), nullable=True)

    # Cultural context
    culture = Column(String(200), nullable=True)
    period = Column(String(200), nullable=True)
    dynasty = Column(String(200), nullable=True)

    # Physical properties
    medium = Column(String(500), nullable=True)
    dimensions = Column(String(500), nullable=True)

    # Classification
    department = Column(String(200), nullable=True)
    classification = Column(String(200), nullable=True)

    # Images
    primary_image = Column(String(500), nullable=True)
    primary_image_small = Column(String(500), nullable=True)

    # Permissions and links
    is_public_domain = Column(Boolean, default=False, nullable=False)
    object_url = Column(String(500), nullable=True)

    # Structured data (stored as JSON)
    constituents = Column(JSONB, nullable=True)

    # Timestamps
    synced_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to generated content
    generated_contents = relationship("GeneratedContent", back_populates="artwork", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Artwork(id={self.id}, met_id={self.met_object_id}, title='{self.title[:50]}...')>"


class GeneratedContent(Base):
    """
    Stores AI-generated content for each artwork
    This includes descriptions, image analysis, and QA status
    """
    __tablename__ = 'generated_content'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to artwork
    artwork_id = Column(Integer, ForeignKey('artworks.id', ondelete='CASCADE'), nullable=False)

    # Generated content
    content = Column(Text, nullable=True)  # The main generated description
    image_analysis = Column(Text, nullable=True)  # AI analysis of the artwork image

    # Quality assurance
    qa_status = Column(String(20), nullable=True, default='pending')  # pending/passed/failed/review
    qa_notes = Column(Text, nullable=True)

    # QR code
    qr_code_url = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to artwork
    artwork = relationship("Artwork", back_populates="generated_contents")

    def __repr__(self):
        return f"<GeneratedContent(id={self.id}, artwork_id={self.artwork_id}, qa_status='{self.qa_status}')>"


# Additional indexes for performance
Index('idx_artwork_department', Artwork.department)
Index('idx_artwork_artist_name', Artwork.artist_display_name)
Index('idx_artwork_is_public_domain', Artwork.is_public_domain)
Index('idx_generated_content_artwork_id', GeneratedContent.artwork_id)
Index('idx_generated_content_qa_status', GeneratedContent.qa_status)