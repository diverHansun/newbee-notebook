"""
BioBERT Embedding 模块

使用本地 BioBERT 模型进行文本嵌入
专为生物医学领域文本优化
"""

from typing import List, Any, Optional, Dict
import torch
from transformers import AutoTokenizer, AutoModel

from .base import BaseEmbeddingModel
from .registry import register_embedding
from src.common.config import get_embeddings_config


class BioBERTEmbedding(BaseEmbeddingModel):
    """BioBERT 嵌入模型实现类

    使用本地或 HuggingFace 的 BioBERT 模型生成文本嵌入向量
    遵循单一职责原则 (SRP)：仅负责 BioBERT 模型的推理逻辑

    Attributes:
        model_name_or_path: 模型路径（本地路径或 HuggingFace 模型名称）
        normalize: 是否对向量进行 L2 归一化（推荐启用以配合余弦相似度）
        device: 运行设备 ('cuda' 或 'cpu')
    """

    def __init__(
        self,
        model_name_or_path: str = "dmis-lab/biobert-v1.1",
        normalize: bool = True,
        device: str = "cpu",
        **kwargs: Any,
    ) -> None:
        """初始化 BioBERT Embedding

        Args:
            model_name_or_path: 模型路径或 HuggingFace 模型 ID
            normalize: 是否进行 L2 归一化（推荐用于余弦相似度）
            device: 运行设备，默认 'cpu'
        """
        super().__init__(**kwargs)

        # Store configuration (use private attributes to avoid Pydantic validation)
        self._model_name_or_path = model_name_or_path
        self._normalize = normalize
        self._device = device

        # 加载模型和分词器
        print(f"[BioBERT] Loading model from: {model_name_or_path}")
        print(f"[BioBERT] Using device: {self._device}")

        try:
            # 尝试本地加载（对于 models/biobert-v1.1）
            self._tokenizer = AutoTokenizer.from_pretrained(
                model_name_or_path,
                local_files_only=True
            )
            self._model = AutoModel.from_pretrained(
                model_name_or_path,
                local_files_only=True
            )
            print(f"[BioBERT] Model loaded from local path")
        except Exception as local_error:
            # 如果本地加载失败，尝试从 HuggingFace 下载
            print(f"[BioBERT] Local loading failed, trying HuggingFace Hub...")
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
                self._model = AutoModel.from_pretrained(model_name_or_path)
                print(f"[BioBERT] Model loaded from HuggingFace Hub")
            except Exception as hub_error:
                raise RuntimeError(
                    f"Failed to load BioBERT model:\n"
                    f"  Local error: {str(local_error)}\n"
                    f"  HuggingFace error: {str(hub_error)}"
                )

        self._model.to(self._device)
        self._model.eval()  # 设置为评估模式

        print(f"[BioBERT] Model loaded successfully (dimension: {self.dimensions})")

    @property
    def dimensions(self) -> int:
        """返回嵌入向量的维度（BioBERT-v1.1 为 768）"""
        return self._model.config.hidden_size

    @property
    def model_name(self) -> str:
        """返回模型名称"""
        return f"biobert-{self._model.config.hidden_size}d"

    def _mean_pooling(
        self,
        last_hidden_state: torch.Tensor,
        attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """对模型输出进行平均池化

        使用 mean pooling 而非 cls token，通常在语义相似度任务中效果更好
        遵循 DRY 原则：池化逻辑集中在单一方法中

        Args:
            last_hidden_state: BERT 最后一层的隐藏状态 [batch_size, seq_len, hidden_size]
            attention_mask: 注意力掩码 [batch_size, seq_len]

        Returns:
            池化后的向量 [batch_size, hidden_size]
        """
        # 扩展 attention_mask 的维度以匹配 hidden_state
        # [batch_size, seq_len, 1] -> [batch_size, seq_len, hidden_size]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()

        # 计算所有 token 的加权和（忽略 padding）
        sum_embeddings = torch.sum(last_hidden_state * input_mask_expanded, 1)

        # 计算每个样本的有效 token 数量
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)

        # 平均池化
        return sum_embeddings / sum_mask

    def _get_query_embedding(self, query: str) -> List[float]:
        """为查询文本生成嵌入向量

        Args:
            query: 查询文本

        Returns:
            嵌入向量（list 格式）
        """
        return self._get_text_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        """为单个文本生成嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量（list 格式）
        """
        return self._get_text_embeddings([text])[0]

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量生成文本嵌入向量

        遵循 KISS 原则：简洁的推理流程
        遵循 SRP 原则：专注于向量生成，池化和归一化逻辑分离

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        # 分词
        encoded = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,  # BioBERT 的最大序列长度
            return_tensors="pt"
        )

        # 移动到对应设备
        encoded = {k: v.to(self._device) for k, v in encoded.items()}

        # 前向传播（不计算梯度）
        with torch.no_grad():
            outputs = self._model(**encoded)
            last_hidden_state = outputs.last_hidden_state

        # Mean pooling
        embeddings = self._mean_pooling(last_hidden_state, encoded["attention_mask"])

        # L2 归一化（用于余弦相似度）
        if self._normalize:
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        # 转换为 numpy 并返回 list
        embeddings_np = embeddings.cpu().numpy()
        return embeddings_np.tolist()


def _get_biobert_config() -> Dict[str, Any]:
    """Get BioBERT-specific configuration from embeddings.yaml.

    Follows SRP: This function has a single responsibility - read BioBERT config.
    Follows DRY: Centralizes BioBERT config reading logic in one place.

    Returns:
        Dictionary containing BioBERT configuration:
        - model_path: Path to model (default: 'models/biobert-v1.1')
        - normalize: Whether to L2 normalize (default: True)
        - device: Device to use (default: 'cpu')
        - dim: Expected embedding dimension (default: 768)

    Example:
        >>> config = _get_biobert_config()
        >>> model_path = config.get('model_path', 'models/biobert-v1.1')
    """
    embeddings_config = get_embeddings_config()
    return embeddings_config.get('embeddings', {}).get('biobert', {})


@register_embedding("biobert")
def build_biobert_embedding(
    model_path: Optional[str] = None,
    normalize: Optional[bool] = None,
    device: Optional[str] = None
) -> BioBERTEmbedding:
    """Build BioBERT Embedding instance.

    Factory function following Dependency Inversion Principle (DIP).
    Automatically registered as 'biobert' provider via decorator.

    Configuration priority:
    1. Function parameters (if provided)
    2. configs/embeddings.yaml (biobert section)
    3. Defaults (models/biobert-v1.1, normalize=True, device='cpu')

    Args:
        model_path: Model path (overrides config if provided)
        normalize: Whether to normalize (overrides config if provided)
        device: Device to use (overrides config if provided)

    Returns:
        BioBERTEmbedding instance

    Example:
        >>> # Use config from embeddings.yaml
        >>> embed_model = build_biobert_embedding()
        >>>
        >>> # Override with custom parameters
        >>> embed_model = build_biobert_embedding(device='cuda')
    """
    # Get configuration from embeddings.yaml
    config = _get_biobert_config()

    # Resolve parameters: arg > config > default
    resolved_model_path = model_path if model_path is not None else config.get('model_path', 'models/biobert-v1.1')
    resolved_normalize = normalize if normalize is not None else config.get('normalize', True)
    resolved_device = device if device is not None else config.get('device', 'cpu')

    return BioBERTEmbedding(
        model_name_or_path=resolved_model_path,
        normalize=resolved_normalize,
        device=resolved_device
    )
