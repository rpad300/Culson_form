import os
import json
import time
import threading
import logging
import hashlib
from typing import Any, Optional, Dict, Callable
from datetime import datetime, timedelta

logger = logging.getLogger('formulario_culsen.file_cache')

class FileCache:
    """
    Sistema de cache em arquivo para otimizar carregamento de dados
    """
    
    def __init__(self, cache_dir: str = None, default_ttl: int = 300):
        """
        Inicializa o sistema de cache
        
        Args:
            cache_dir: Diretório para armazenar arquivos de cache
            default_ttl: TTL padrão em segundos (5 minutos)
        """
        if cache_dir is None:
            # Usar diretório cache na raiz do projeto
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cache_dir = os.path.join(current_dir, 'cache')
        
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
        
        # TTLs específicos para diferentes tipos de dados
        self.ttl_config = {
            'config': 1800,      # 30 minutos para configurações
            'candidates': 300,   # 5 minutos para candidatos
            'questions': 600,    # 10 minutos para perguntas
            'forms': 900,        # 15 minutos para formulários
            'api_status': 120,   # 2 minutos para status de APIs
        }
        
        # Criar diretório de cache se não existir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        logger.info(f"FileCache inicializado em: {self.cache_dir}")
    
    def _get_cache_file_path(self, key: str) -> str:
        """Gera o caminho do arquivo de cache para uma chave"""
        # Criar hash da chave para evitar problemas com caracteres especiais
        key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{key_hash}.json")
    
    def _get_ttl_for_key(self, key: str) -> int:
        """Retorna o TTL apropriado baseado na chave"""
        for cache_type, ttl in self.ttl_config.items():
            if cache_type in key.lower():
                return ttl
        return self.default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """
        Obtém um valor do cache se ainda for válido
        
        Args:
            key: Chave do cache
            
        Returns:
            Valor do cache ou None se não existir/expirado
        """
        with self._lock:
            cache_file = self._get_cache_file_path(key)
            
            if not os.path.exists(cache_file):
                return None
            
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Verificar se o cache expirou
                cached_time = cache_data.get('timestamp', 0)
                ttl = self._get_ttl_for_key(key)
                
                if time.time() - cached_time > ttl:
                    # Cache expirado, remover arquivo
                    os.remove(cache_file)
                    logger.info(f"Cache expirado removido: {key}")
                    return None
                
                logger.info(f"Cache hit para: {key}")
                return cache_data.get('data')
                
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"Erro ao ler cache {key}: {str(e)}")
                # Remover arquivo corrompido
                try:
                    os.remove(cache_file)
                except:
                    pass
                return None
    
    def set(self, key: str, value: Any) -> bool:
        """
        Define um valor no cache
        
        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            
        Returns:
            True se salvou com sucesso, False caso contrário
        """
        with self._lock:
            cache_file = self._get_cache_file_path(key)
            
            try:
                cache_data = {
                    'timestamp': time.time(),
                    'key': key,
                    'data': value
                }
                
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Cache salvo para: {key}")
                return True
                
            except (OSError, TypeError) as e:
                logger.error(f"Erro ao salvar cache {key}: {str(e)}")
                return False
    
    def invalidate(self, key: str) -> bool:
        """
        Remove uma chave específica do cache
        
        Args:
            key: Chave a ser removida
            
        Returns:
            True se removeu com sucesso, False caso contrário
        """
        with self._lock:
            cache_file = self._get_cache_file_path(key)
            
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    logger.info(f"Cache invalidado: {key}")
                    return True
                return False
                
            except OSError as e:
                logger.error(f"Erro ao invalidar cache {key}: {str(e)}")
                return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Remove todas as chaves que contêm o padrão
        
        Args:
            pattern: Padrão a ser procurado nas chaves
            
        Returns:
            Número de chaves removidas
        """
        removed_count = 0
        
        with self._lock:
            try:
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.json'):
                        cache_file = os.path.join(self.cache_dir, filename)
                        
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            
                            key = cache_data.get('key', '')
                            if pattern.lower() in key.lower():
                                os.remove(cache_file)
                                logger.info(f"Cache invalidado por padrão: {key}")
                                removed_count += 1
                                
                        except (json.JSONDecodeError, KeyError, OSError):
                            # Arquivo corrompido, remover
                            try:
                                os.remove(cache_file)
                                removed_count += 1
                            except:
                                pass
                
            except OSError as e:
                logger.error(f"Erro ao invalidar por padrão {pattern}: {str(e)}")
        
        logger.info(f"Invalidados {removed_count} caches com padrão: {pattern}")
        return removed_count
    
    def clear(self) -> int:
        """
        Limpa todo o cache
        
        Returns:
            Número de arquivos removidos
        """
        removed_count = 0
        
        with self._lock:
            try:
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.json'):
                        cache_file = os.path.join(self.cache_dir, filename)
                        try:
                            os.remove(cache_file)
                            removed_count += 1
                        except OSError:
                            pass
                
            except OSError as e:
                logger.error(f"Erro ao limpar cache: {str(e)}")
        
        logger.info(f"Cache limpo: {removed_count} arquivos removidos")
        return removed_count
    
    def cleanup_expired(self) -> int:
        """
        Remove arquivos de cache expirados
        
        Returns:
            Número de arquivos removidos
        """
        removed_count = 0
        current_time = time.time()
        
        with self._lock:
            try:
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.json'):
                        cache_file = os.path.join(self.cache_dir, filename)
                        
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            
                            cached_time = cache_data.get('timestamp', 0)
                            key = cache_data.get('key', '')
                            ttl = self._get_ttl_for_key(key)
                            
                            if current_time - cached_time > ttl:
                                os.remove(cache_file)
                                logger.info(f"Cache expirado removido: {key}")
                                removed_count += 1
                                
                        except (json.JSONDecodeError, KeyError, OSError):
                            # Arquivo corrompido, remover
                            try:
                                os.remove(cache_file)
                                removed_count += 1
                            except:
                                pass
                
            except OSError as e:
                logger.error(f"Erro ao limpar caches expirados: {str(e)}")
        
        if removed_count > 0:
            logger.info(f"Limpeza de cache: {removed_count} arquivos expirados removidos")
        
        return removed_count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do cache
        
        Returns:
            Dicionário com estatísticas
        """
        stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'expired_files': 0,
            'valid_files': 0,
            'cache_keys': [],
            'cache_dir': self.cache_dir
        }
        
        current_time = time.time()
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    cache_file = os.path.join(self.cache_dir, filename)
                    
                    try:
                        file_size = os.path.getsize(cache_file)
                        stats['total_files'] += 1
                        stats['total_size_bytes'] += file_size
                        
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        
                        key = cache_data.get('key', '')
                        cached_time = cache_data.get('timestamp', 0)
                        ttl = self._get_ttl_for_key(key)
                        
                        if current_time - cached_time > ttl:
                            stats['expired_files'] += 1
                        else:
                            stats['valid_files'] += 1
                            stats['cache_keys'].append(key)
                            
                    except (json.JSONDecodeError, KeyError, OSError):
                        stats['expired_files'] += 1
                        
        except OSError:
            pass
        
        # Converter bytes para MB
        stats['total_size_mb'] = round(stats['total_size_bytes'] / 1024 / 1024, 2)
        
        return stats

def with_file_cache(cache_key: str, fetch_function: Callable, force_refresh: bool = False, cache_instance: FileCache = None) -> Any:
    """
    Decorator/helper para implementar cache em arquivo com fallback
    
    Args:
        cache_key: Chave para o cache
        fetch_function: Função para buscar dados se não estiver em cache
        force_refresh: Se True, força a atualização do cache
        cache_instance: Instância do cache a usar (opcional)
    
    Returns:
        Dados do cache ou resultado da função
    """
    if cache_instance is None:
        # Usar instância global padrão
        cache_instance = default_file_cache
    
    try:
        # Se não for refresh forçado, tentar cache primeiro
        if not force_refresh:
            cached_data = cache_instance.get(cache_key)
            if cached_data is not None:
                return cached_data
        
        # Buscar dados frescos
        logger.info(f"Buscando dados frescos para: {cache_key}")
        fresh_data = fetch_function()
        
        # Salvar no cache
        cache_instance.set(cache_key, fresh_data)
        
        return fresh_data
        
    except Exception as e:
        logger.error(f"Erro ao buscar dados frescos para {cache_key}: {str(e)}")
        
        # Em caso de erro, tentar usar cache mesmo que expirado
        try:
            cache_file = cache_instance._get_cache_file_path(cache_key)
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                logger.warning(f"Usando cache expirado devido a erro para: {cache_key}")
                return cache_data.get('data')
        except:
            pass
        
        # Se não há cache, re-raise o erro
        raise e

# Instância global padrão
default_file_cache = FileCache()

# Função para limpeza automática (pode ser chamada periodicamente)
def auto_cleanup():
    """Executa limpeza automática de caches expirados"""
    try:
        removed = default_file_cache.cleanup_expired()
        if removed > 0:
            logger.info(f"Limpeza automática: {removed} caches expirados removidos")
    except Exception as e:
        logger.error(f"Erro na limpeza automática: {str(e)}") 