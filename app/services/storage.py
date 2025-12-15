"""
Google Cloud Storage Service
AWS S3 대신 Google Cloud Storage 사용
"""

import os
import uuid
from datetime import timedelta
from typing import Optional
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError


class CloudStorageService:
    """Google Cloud Storage 파일 관리 서비스"""
    
    def __init__(self):
        self.bucket_name = os.getenv("GCS_BUCKET", "local-seo-optimizer-files")
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None
    
    @property
    def client(self) -> storage.Client:
        """Lazy initialization of storage client"""
        if self._client is None:
            self._client = storage.Client()
        return self._client
    
    @property
    def bucket(self) -> storage.Bucket:
        """Get or create bucket"""
        if self._bucket is None:
            self._bucket = self.client.bucket(self.bucket_name)
        return self._bucket
    
    def upload_file(
        self, 
        file_data: bytes, 
        filename: str, 
        content_type: str = "application/octet-stream",
        folder: str = "uploads"
    ) -> str:
        """
        파일 업로드
        
        Args:
            file_data: 파일 바이트 데이터
            filename: 원본 파일명
            content_type: MIME 타입
            folder: 저장 폴더
            
        Returns:
            업로드된 파일의 공개 URL
        """
        try:
            # 고유 파일명 생성
            ext = filename.split(".")[-1] if "." in filename else ""
            unique_name = f"{folder}/{uuid.uuid4().hex}"
            if ext:
                unique_name += f".{ext}"
            
            blob = self.bucket.blob(unique_name)
            blob.upload_from_string(file_data, content_type=content_type)
            
            # 공개 URL 반환
            return f"https://storage.googleapis.com/{self.bucket_name}/{unique_name}"
            
        except GoogleCloudError as e:
            raise Exception(f"Failed to upload file: {str(e)}")
    
    def upload_from_file(
        self,
        file_path: str,
        destination_name: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """로컬 파일 업로드"""
        try:
            blob = self.bucket.blob(destination_name)
            blob.upload_from_filename(file_path, content_type=content_type)
            return f"https://storage.googleapis.com/{self.bucket_name}/{destination_name}"
        except GoogleCloudError as e:
            raise Exception(f"Failed to upload file: {str(e)}")
    
    def get_signed_url(
        self, 
        blob_name: str, 
        expiration_minutes: int = 60
    ) -> str:
        """
        서명된 URL 생성 (임시 접근용)
        
        Args:
            blob_name: 파일 경로
            expiration_minutes: 만료 시간 (분)
            
        Returns:
            서명된 URL
        """
        try:
            blob = self.bucket.blob(blob_name)
            url = blob.generate_signed_url(
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            return url
        except GoogleCloudError as e:
            raise Exception(f"Failed to generate signed URL: {str(e)}")
    
    def delete_file(self, blob_name: str) -> bool:
        """파일 삭제"""
        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            return True
        except GoogleCloudError as e:
            print(f"Failed to delete file: {str(e)}")
            return False
    
    def file_exists(self, blob_name: str) -> bool:
        """파일 존재 여부 확인"""
        blob = self.bucket.blob(blob_name)
        return blob.exists()
    
    def list_files(self, prefix: str = "") -> list:
        """폴더 내 파일 목록"""
        blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
        return [blob.name for blob in blobs]


# 싱글톤 인스턴스
_storage_service: Optional[CloudStorageService] = None


def get_storage_service() -> CloudStorageService:
    """Storage 서비스 인스턴스 반환"""
    global _storage_service
    if _storage_service is None:
        _storage_service = CloudStorageService()
    return _storage_service
