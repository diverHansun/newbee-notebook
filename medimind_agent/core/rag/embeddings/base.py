"""
Embedding 妯″瀷鍩虹绫?
瀹氫箟缁熶竴鐨?embedding 鎺ュ彛锛岄伒寰紑鏀惧皝闂師鍒?(OCP)
"""

from abc import ABC, abstractmethod
from typing import List
from llama_index.core.embeddings import BaseEmbedding


class BaseEmbeddingModel(BaseEmbedding):
    """Embedding 妯″瀷鎶借薄鍩虹被

    鎵€鏈夎嚜瀹氫箟 embedding 妯″瀷搴旂户鎵挎绫伙紝纭繚鎺ュ彛涓€鑷存€?    閬靛惊鍗曚竴鑱岃矗鍘熷垯 (SRP)锛氫粎瀹氫箟 embedding 鐨勯€氱敤鎺ュ彛
    """

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """杩斿洖宓屽叆鍚戦噺鐨勭淮搴?
        Returns:
            int: 鍚戦噺缁村害锛堝 768, 1024 绛夛級
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """杩斿洖妯″瀷鍚嶇О锛岀敤浜庢棩蹇楀拰璋冭瘯

        Returns:
            str: 妯″瀷鍚嶇О锛堝 'biobert-v1.1', 'zhipu-embedding-3'锛?        """
        pass

    @abstractmethod
    def _get_query_embedding(self, query: str) -> List[float]:
        """涓烘煡璇㈡枃鏈敓鎴愬祵鍏ュ悜閲?
        Args:
            query: 鏌ヨ鏂囨湰

        Returns:
            宓屽叆鍚戦噺
        """
        pass

    @abstractmethod
    def _get_text_embedding(self, text: str) -> List[float]:
        """涓哄崟涓枃鏈敓鎴愬祵鍏ュ悜閲?
        Args:
            text: 杈撳叆鏂囨湰

        Returns:
            宓屽叆鍚戦噺
        """
        pass

    @abstractmethod
    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """鎵归噺鐢熸垚鏂囨湰宓屽叆鍚戦噺

        Args:
            texts: 鏂囨湰鍒楄〃

        Returns:
            宓屽叆鍚戦噺鍒楄〃
        """
        pass

    async def _aget_query_embedding(self, query: str) -> List[float]:
        """寮傛鑾峰彇鏌ヨ宓屽叆锛堥粯璁や娇鐢ㄥ悓姝ュ疄鐜帮級

        瀛愮被鍙鐩栨鏂规硶浠ユ彁渚涚湡姝ｇ殑寮傛瀹炵幇
        """
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        """寮傛鑾峰彇鏂囨湰宓屽叆锛堥粯璁や娇鐢ㄥ悓姝ュ疄鐜帮級

        瀛愮被鍙鐩栨鏂规硶浠ユ彁渚涚湡姝ｇ殑寮傛瀹炵幇
        """
        return self._get_text_embedding(text)

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """寮傛鎵归噺鑾峰彇鏂囨湰宓屽叆锛堥粯璁や娇鐢ㄥ悓姝ュ疄鐜帮級

        瀛愮被鍙鐩栨鏂规硶浠ユ彁渚涚湡姝ｇ殑寮傛瀹炵幇
        """
        return self._get_text_embeddings(texts)


