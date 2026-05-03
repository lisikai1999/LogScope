import base64
import os
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


def derive_key_from_secret(secret: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """
    从密钥派生出 Fernet 密钥
    
    Args:
        secret: 原始密钥字符串
        salt: 盐值，如果为 None 则生成新的
    
    Returns:
        (derived_key, salt) 派生的密钥和使用的盐值
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return key, salt


def get_encryption_key(secret: str = None) -> bytes:
    """
    获取加密密钥
    
    优先使用环境变量 ENCRYPTION_KEY，如果没有则从 SECRET_KEY 派生。
    为了保持密钥一致性，我们使用固定的盐值。
    """
    encryption_key = os.environ.get("ENCRYPTION_KEY")
    
    if encryption_key:
        try:
            key_bytes = base64.urlsafe_b64decode(encryption_key)
            if len(key_bytes) == 32:
                return base64.urlsafe_b64encode(key_bytes)
        except Exception:
            pass
    
    if secret is None:
        from config import settings
        secret = settings.SECRET_KEY
    
    fixed_salt = b'logscope_encryption_salt_2024'
    key, _ = derive_key_from_secret(secret, fixed_salt)
    return key


class EncryptionService:
    """
    加密服务，用于加密和解密敏感数据
    
    使用 Fernet 对称加密算法，保证数据的机密性和完整性。
    """
    
    def __init__(self, key: bytes = None):
        """
        初始化加密服务
        
        Args:
            key: Fernet 密钥（32字节，base64编码），如果为 None 则自动获取
        """
        if key is None:
            key = get_encryption_key()
        
        self._fernet = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密字符串
        
        Args:
            plaintext: 要加密的明文字符串
        
        Returns:
            加密后的字符串（base64编码）
        """
        if plaintext is None:
            return None
        
        encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        解密字符串
        
        Args:
            ciphertext: 加密后的字符串（base64编码）
        
        Returns:
            解密后的明文字符串，如果解密失败则返回 None
        """
        if ciphertext is None:
            return None
        
        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception:
            return None
    
    def encrypt_dict_values(self, data: dict, keys: list) -> dict:
        """
        加密字典中的指定字段
        
        Args:
            data: 原始字典
            keys: 需要加密的键名列表
        
        Returns:
            加密后的字典
        """
        result = data.copy()
        for key in keys:
            if key in result and result[key] is not None:
                result[key] = self.encrypt(result[key])
        return result
    
    def decrypt_dict_values(self, data: dict, keys: list) -> dict:
        """
        解密字典中的指定字段
        
        Args:
            data: 加密后的字典
            keys: 需要解密的键名列表
        
        Returns:
            解密后的字典
        """
        result = data.copy()
        for key in keys:
            if key in result and result[key] is not None:
                decrypted = self.decrypt(result[key])
                if decrypted is not None:
                    result[key] = decrypted
        return result


_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """
    获取加密服务单例
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt(plaintext: str) -> str:
    """
    便捷函数：加密字符串
    """
    return get_encryption_service().encrypt(plaintext)


def decrypt(ciphertext: str) -> Optional[str]:
    """
    便捷函数：解密字符串
    """
    return get_encryption_service().decrypt(ciphertext)
