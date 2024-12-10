# database/models.py
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator
import re

class LaptopSpecs(BaseModel):
    processor: Dict[str, str] = Field(
        default_factory=lambda: {
            "brand": "",
            "model": "",
            "generation": "",
            "speed": "",
            "cores": ""
        },
        description="Processor details including brand, model, generation"
    )
    
    ram: Dict[str, str] = Field(
        default_factory=lambda: {
            "size": "",
            "type": "",
            "speed": ""
        },
        description="RAM details including size and type"
    )
    
    storage: Dict[str, str] = Field(
        default_factory=lambda: {
            "primary_type": "",
            "primary_capacity": "",
            "secondary_type": "",
            "secondary_capacity": ""
        },
        description="Storage details including type and capacity"
    )
    
    display: Dict[str, str] = Field(
        default_factory=lambda: {
            "size": "",
            "resolution": "",
            "type": "",
            "refresh_rate": "",
            "nits": ""
        },
        description="Display details including size, resolution, type"
    )
    
    graphics: Dict[str, str] = Field(
        default_factory=lambda: {
            "type": "",
            "brand": "",
            "model": "",
            "memory": ""
        },
        description="Graphics card information"
    )
    
    os: str = Field(
        default="",
        description="Operating system"
    )
    
    battery: Dict[str, str] = Field(
        default_factory=lambda: {
            "capacity": "",
            "type": "",
            "watt_hours": "",
            "cells": ""
        },
        description="Battery specifications"
    )
    
    ports: List[str] = Field(
        default_factory=list,
        description="Available ports and connectivity options"
    )
    
    dimensions: Dict[str, float] = Field(
        default_factory=lambda: {
            "length": 0.0,
            "width": 0.0,
            "height": 0.0,
            "weight": 0.0
        },
        description="Physical dimensions and weight"
    )
    
    additional_features: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional features like fingerprint reader, backlit keyboard, etc."
    )

class PriceHistory(BaseModel):
    price: float
    date: datetime
    source: str

class Laptop(BaseModel):
    product_id: str = Field(..., description="Unique identifier")
    source: str = Field(..., description="Source website (e.g., Amazon, Flipkart)")
    url: str = Field(..., description="Product URL")
    title: str = Field(..., description="Product title")
    brand: str = Field(..., description="Laptop brand")
    model: str = Field(..., description="Model number/name")
    current_price: float = Field(..., description="Current selling price")
    original_price: float = Field(..., description="Original MRP")
    ratings_count: int = Field(default=0, description="Number of ratings")
    average_rating: float = Field(default=0.0, description="Average rating")
    specifications: LaptopSpecs = Field(..., description="Technical specifications")
    in_stock: bool = Field(default=True, description="Availability status")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    price_history: List[PriceHistory] = Field(default_factory=list)
    
    @validator('current_price', 'original_price')
    def validate_price(cls, v):
        if v < 0:
            raise ValueError("Price cannot be negative")
        return round(v, 2)
    
    @validator('average_rating')
    def validate_rating(cls, v):
        if not 0 <= v <= 5:
            raise ValueError("Rating must be between 0 and 5")
        return round(v, 1)
    
    @validator('product_id')
    def validate_product_id(cls, v):
        if not v.strip():
            raise ValueError("Product ID cannot be empty")
        return v.strip()