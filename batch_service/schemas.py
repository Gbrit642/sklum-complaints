from pydantic import BaseModel, Field


class ComplaintAnalysis(BaseModel):
    complaint_id: str
    original_text: str = Field(default="", description="Masked complaint text")
    category: str = ""
    subcategory: str = ""
    priority: str = "rutinario"
    priority_reasoning: str = ""
    sentiment_score: float = 0.0
    product_sku: str | None = None
    product_name: str | None = None
    damage_type: str | None = None
    image_analysis_summary: str | None = None
    has_image: bool = False
    key_excerpt: str = ""
    suggested_action: str = ""


class PatternCluster(BaseModel):
    pattern_id: str
    theme: str
    description: str
    complaint_ids: list[str]
    frequency: int
    trend: str
    root_cause_hypothesis: str


class CategoryBreakdown(BaseModel):
    category: str
    count: int
    percentage: float
    avg_sentiment: float


class TopSku(BaseModel):
    sku: str
    product_name: str
    complaint_count: int
    main_issue: str


class ImageAnalysisSummary(BaseModel):
    total_images: int
    damage_types: dict[str, int]


class BatchAnalysisRequest(BaseModel):
    dataset_gcs_path: str


class BatchAnalysisResponse(BaseModel):
    status: str
    total_complaints: int
    analysis_timestamp: str
    complaints: list[ComplaintAnalysis]
    patterns: list[PatternCluster]
    category_breakdown: list[CategoryBreakdown]
    top_skus: list[TopSku]
    urgent_count: int
    systemic_count: int
    routine_count: int
    image_analysis_summary: ImageAnalysisSummary
