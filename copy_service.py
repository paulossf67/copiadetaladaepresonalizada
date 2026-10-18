import shutil
import os
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Callable, Optional
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2
import base64
import schedule


class CopyService:
    """Serviço de cópia de arquivos com monitoramento de progresso"""

    def __init__(self, on_progress: Optional[Callable] = None, on_error: Optional[Callable] = None):
        self.on_progress = on_progress
        self.on_error = on_error
        self.is_cancelled = False
        self.is_paused = False

    def cancel(self):
        """Cancela a operação em progresso"""
        self.is_cancelled = True

    def pause(self):
        """Pausa a operação em progresso"""
        self.is_paused = True

    def resume(self):
        """Retoma a operação pausada"""
        self.is_paused = False

    def reset_flags(self):
        """Reseta flags de controle"""
        self.is_cancelled = False
        self.is_paused = False

    @staticmethod
    def calculate_hash(file_path: str, algorithm: str = "md5") -> str:
        """Calcula hash de um arquivo"""
        hash_obj = hashlib.new(algorithm)
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except (OSError, IOError):
            return ""

    def copy_with_progress(self, source: str, destination: str) -> Dict:
        """Copia arquivos com monitoramento de progresso"""
        try:
            source_path = Path(source)
            dest_path = Path(destination)

            # Validações
            if not source_path.exists() or not (source_path.is_file() or source_path.is_dir()):
                raise ValueError(f"Caminho de origem inválido: {source}")

            source_resolved = source_path.resolve()
            dest_resolved = dest_path.resolve()

            # Validar se destino está dentro da origem
            if source_path.is_dir():
                try:
                    dest_resolved.relative_to(source_resolved)
                except ValueError:
                    pass
                else:
                    raise ValueError("O destino não pode estar dentro da pasta de origem.")
            elif (dest_resolved / source_path.name).resolve() == source_resolved:
                raise ValueError("O arquivo de destino não pode ser o próprio arquivo de origem.")

            dest_path.mkdir(parents=True, exist_ok=True)

            # Coletar estatísticas
            stats = self._collect_stats(source_path)
            total_files = stats['total_files']
            total_size = stats['total_size']

            # Iniciar operação
            start_time = time.time()
            files_copied = 0
            files_processed = 0
            failed_files = 0
            bytes_copied = 0
            failed_list = []

            files = [source_path] if source_path.is_file() else (
                Path(root) / filename
                for root, _, filenames in os.walk(source_path, onerror=self._raise_walk_error)
                for filename in filenames
            )

            for src_file in files:
                # Verificar se foi solicitado cancelamento
                if self.is_cancelled:
                    return {
                        "status": "cancelled",
                        "message": "Operação cancelada pelo usuário",
                        "files_copied": files_copied,
                        "failed_files": failed_files,
                        "total_size_mb": round(bytes_copied / (1024 * 1024), 2),
                        "total_time": round(time.time() - start_time, 2)
                    }

                # Aguardar se pausa foi solicitada
                while self.is_paused:
                    time.sleep(0.1)

                rel_path = src_file.name if source_path.is_file() else src_file.relative_to(source_path)
                dest_file = dest_path / rel_path

                try:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    file_size = os.path.getsize(src_file)
                    shutil.copy2(src_file, dest_file)
                    bytes_copied += file_size
                    files_copied += 1
                except OSError as error:
                    failed_files += 1
                    failed_list.append({
                        "file": str(src_file),
                        "error": str(error)
                    })
                    if self.on_error:
                        self.on_error(str(src_file), str(error))
                finally:
                    files_processed += 1

                elapsed = time.time() - start_time
                speed_mbps = (bytes_copied / (1024 * 1024)) / (elapsed + 0.1)
                progress = (files_processed / total_files * 100) if total_files > 0 else 0

                if self.on_progress:
                    self.on_progress({
                        "current_file": str(src_file.name),
                        "files_copied": files_copied,
                        "total_files": total_files,
                        "bytes_copied": bytes_copied,
                        "total_bytes": total_size,
                        "progress_percent": progress,
                        "speed_mbps": round(speed_mbps, 2),
                        "elapsed_time": round(elapsed, 2)
                    })

            # Finalizar
            total_elapsed = time.time() - start_time
            final_speed = (bytes_copied / (1024 * 1024)) / (total_elapsed + 0.1)

            result = {
                "status": "partial" if (failed_files and files_copied) else ("failed" if failed_files else "completed"),
                "files_copied": files_copied,
                "failed_files": failed_files,
                "failed_list": failed_list,
                "total_size_mb": round(bytes_copied / (1024 * 1024), 2),
                "total_time": round(total_elapsed, 2),
                "average_speed_mbps": round(final_speed, 2),
                "file_types": stats['file_types'],
                "timestamp": datetime.now().isoformat()
            }

            # Salvar histórico
            try:
                self._save_history({
                    "source": source,
                    "destination": destination,
                    "files_copied": files_copied,
                    "failed_files": failed_files,
                    "size_mb": round(bytes_copied / (1024 * 1024), 2),
                    "time_seconds": round(total_elapsed, 2),
                    "speed_mbps": round(final_speed, 2),
                    "timestamp": datetime.now().isoformat()
                })
            except OSError as error:
                result["history_warning"] = f"Não foi possível salvar o histórico: {error}"

            return result

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    def move_with_progress(self, source: str, destination: str) -> Dict:
        """Move arquivos com monitoramento de progresso (copia + deleta)"""
        try:
            # Primeiro, copia os arquivos
            result = self.copy_with_progress(source, destination)

            # Se a cópia foi bem-sucedida e todos os arquivos foram copiados, deleta a origem
            if result["status"] != "error" and result.get("files_copied", 0) > 0:
                try:
                    source_path = Path(source)

                    # Se for arquivo, delete o arquivo
                    if source_path.is_file():
                        source_path.unlink()
                    # Se for diretório, delete recursivamente
                    else:
                        shutil.rmtree(source_path)

                    result["operation"] = "move"
                except Exception as e:
                    # Se falhar ao deletar, ainda assim retorna sucesso mas com aviso
                    result["move_error"] = f"Arquivos foram copiados mas não removidos da origem: {str(e)}"

            return result
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def _raise_walk_error(error: OSError):
        raise error

    @staticmethod
    def _collect_stats(path: Path) -> Dict:
        """Coleta estatísticas sobre os arquivos"""
        stats = {
            'total_files': 0,
            'total_size': 0,
            'file_types': {}
        }

        if path.is_file():
            stats['total_files'] = 1
            stats['total_size'] = path.stat().st_size
            ext = path.suffix or 'sem_extensão'
            stats['file_types'][ext] = 1
        else:
            for root, _, files in os.walk(path, onerror=CopyService._raise_walk_error):
                for file in files:
                    file_path = Path(root) / file
                    stats['total_files'] += 1
                    stats['total_size'] += file_path.stat().st_size
                    ext = file_path.suffix or 'sem_extensão'
                    stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1

        return stats

    @staticmethod
    def get_path_info(path: str) -> Dict:
        """Obtém informações sobre um caminho"""
        try:
            p = Path(path)
            if p.exists():
                if p.is_dir():
                    stats = CopyService._collect_stats(p)
                    return {
                        "valid": True,
                        "type": "directory",
                        "file_count": stats['total_files'],
                        "size_mb": round(stats['total_size'] / (1024 * 1024), 2)
                    }
                else:
                    return {
                        "valid": True,
                        "type": "file",
                        "size_mb": round(p.stat().st_size / (1024 * 1024), 2)
                    }
            return {"valid": False, "message": "Caminho não encontrado"}
        except Exception as e:
            return {"valid": False, "message": str(e)}

    @staticmethod
    def check_file_access(file_path: str) -> Dict:
        """Verifica se o arquivo pode ser lido por completo"""
        try:
            path = Path(file_path)

            if not path.exists():
                return {"status": "not_found", "message": "Arquivo não encontrado"}
            if not path.is_file():
                return {"status": "not_file", "message": "O caminho informado não é um arquivo"}

            with open(path, "rb") as f:
                while f.read(1024 * 1024):
                    pass

            return {
                "status": "accessible",
                "file": path.name,
                "size": path.stat().st_size,
                "accessible": True
            }
        except OSError as e:
            return {
                "status": "unreadable",
                "file": path.name if path.exists() else "desconhecido",
                "error": str(e),
                "accessible": False
            }

    def verify_copy_integrity(self, source: str, destination: str) -> Dict:
        """Verifica integridade dos arquivos copiados usando hash MD5"""
        try:
            source_path = Path(source)
            dest_path = Path(destination)

            if not source_path.exists() or not dest_path.exists():
                return {"status": "error", "message": "Caminho de origem ou destino não encontrado"}

            corrupted = []
            verified = 0
            failed = 0

            files = [source_path] if source_path.is_file() else (
                Path(root) / filename
                for root, _, filenames in os.walk(source_path)
                for filename in filenames
            )

            for src_file in files:
                rel_path = src_file.name if source_path.is_file() else src_file.relative_to(source_path)
                dest_file = dest_path / rel_path

                if not dest_file.exists():
                    corrupted.append({"file": str(rel_path), "reason": "Arquivo não encontrado no destino"})
                    failed += 1
                    continue

                src_hash = self.calculate_hash(str(src_file))
                dest_hash = self.calculate_hash(str(dest_file))

                if src_hash == dest_hash:
                    verified += 1
                else:
                    corrupted.append({"file": str(rel_path), "reason": "Hash diferente - arquivo corrompido"})
                    failed += 1

            return {
                "status": "completed",
                "verified": verified,
                "failed": failed,
                "corrupted_files": corrupted,
                "total": verified + failed
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _save_history(record: Dict):
        """Salva histórico de operações"""
        history_file = Path("history.json")
        history = []

        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError):
                history = []

        history.append(record)

        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    @staticmethod
    def get_history() -> list:
        """Obtém histórico de operações"""
        history_file = Path("history.json")
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []


class ParallelCopyService(CopyService):
    """Serviço de cópia com multi-threading paralelo (3 arquivos simultâneos)"""

    def __init__(self, on_progress: Optional[Callable] = None, on_error: Optional[Callable] = None, max_workers: int = 3):
        super().__init__(on_progress, on_error)
        self.max_workers = max_workers
        self.progress_lock = Lock()

    def copy_with_progress_parallel(self, source: str, destination: str) -> Dict:
        """Copia múltiplos arquivos em paralelo (até 3 simultâneos)"""
        try:
            source_path = Path(source)
            dest_path = Path(destination)

            # Validações
            if not source_path.exists() or not (source_path.is_file() or source_path.is_dir()):
                raise ValueError(f"Caminho de origem inválido: {source}")

            source_resolved = source_path.resolve()
            dest_resolved = dest_path.resolve()

            # Validar se destino está dentro da origem
            if source_path.is_dir():
                try:
                    dest_resolved.relative_to(source_resolved)
                except ValueError:
                    pass
                else:
                    raise ValueError("O destino não pode estar dentro da pasta de origem.")
            elif (dest_resolved / source_path.name).resolve() == source_resolved:
                raise ValueError("O arquivo de destino não pode ser o próprio arquivo de origem.")

            dest_path.mkdir(parents=True, exist_ok=True)

            # Coletar estatísticas
            stats = self._collect_stats(source_path)
            total_files = stats['total_files']
            total_size = stats['total_size']

            # Iniciar operação
            start_time = time.time()
            files_copied = 0
            files_processed = 0
            failed_files = 0
            bytes_copied = 0
            failed_list = []

            files = [source_path] if source_path.is_file() else list(
                Path(root) / filename
                for root, _, filenames in os.walk(source_path, onerror=self._raise_walk_error)
                for filename in filenames
            )

            # Usar ThreadPoolExecutor para cópia paralela
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {}

                for src_file in files:
                    if self.is_cancelled:
                        break

                    # Aguardar se pausa foi solicitada
                    while self.is_paused:
                        time.sleep(0.1)

                    rel_path = src_file.name if source_path.is_file() else src_file.relative_to(source_path)
                    dest_file = dest_path / rel_path

                    future = executor.submit(self._copy_single_file, src_file, dest_file)
                    future_to_file[future] = (src_file, dest_file, src_file.stat().st_size)

                # Processar resultados conforme completam
                for future in as_completed(future_to_file):
                    if self.is_cancelled:
                        break

                    src_file, dest_file, file_size = future_to_file[future]
                    try:
                        success = future.result()
                        if success:
                            bytes_copied += file_size
                            files_copied += 1
                        else:
                            failed_files += 1
                            failed_list.append({
                                "file": str(src_file),
                                "error": "Falha ao copiar arquivo"
                            })
                    except Exception as e:
                        failed_files += 1
                        failed_list.append({
                            "file": str(src_file),
                            "error": str(e)
                        })
                        if self.on_error:
                            self.on_error(str(src_file), str(e))
                    finally:
                        files_processed += 1

                    elapsed = time.time() - start_time
                    speed_mbps = (bytes_copied / (1024 * 1024)) / (elapsed + 0.1)
                    progress = (files_processed / total_files * 100) if total_files > 0 else 0

                    if self.on_progress:
                        with self.progress_lock:
                            self.on_progress({
                                "current_file": str(src_file.name),
                                "files_copied": files_copied,
                                "total_files": total_files,
                                "bytes_copied": bytes_copied,
                                "total_bytes": total_size,
                                "progress_percent": progress,
                                "speed_mbps": round(speed_mbps, 2),
                                "elapsed_time": round(elapsed, 2),
                                "parallel": True,
                                "active_threads": min(self.max_workers, len(future_to_file))
                            })

            # Finalizar
            total_elapsed = time.time() - start_time
            final_speed = (bytes_copied / (1024 * 1024)) / (total_elapsed + 0.1)

            result = {
                "status": "partial" if (failed_files and files_copied) else ("failed" if failed_files else "completed"),
                "files_copied": files_copied,
                "failed_files": failed_files,
                "failed_list": failed_list,
                "total_size_mb": round(bytes_copied / (1024 * 1024), 2),
                "total_time": round(total_elapsed, 2),
                "average_speed_mbps": round(final_speed, 2),
                "file_types": stats['file_types'],
                "timestamp": datetime.now().isoformat(),
                "parallel_mode": True,
                "max_workers": self.max_workers
            }

            # Salvar histórico
            try:
                self._save_history({
                    "source": source,
                    "destination": destination,
                    "files_copied": files_copied,
                    "failed_files": failed_files,
                    "size_mb": round(bytes_copied / (1024 * 1024), 2),
                    "time_seconds": round(total_elapsed, 2),
                    "speed_mbps": round(final_speed, 2),
                    "timestamp": datetime.now().isoformat(),
                    "parallel_mode": True
                })
            except OSError as error:
                result["history_warning"] = f"Não foi possível salvar o histórico: {error}"

            return result

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    def _copy_single_file(self, src_file: Path, dest_file: Path) -> bool:
        """Copia um arquivo único (para uso em paralelo)"""
        try:
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest_file)
            return True
        except OSError as error:
            if self.on_error:
                self.on_error(str(src_file), str(error))
            return False

    def move_with_progress_parallel(self, source: str, destination: str) -> Dict:
        """Move arquivos com multi-threading paralelo (copia + deleta)"""
        try:
            # Primeiro, copia os arquivos em paralelo
            result = self.copy_with_progress_parallel(source, destination)

            # Se a cópia foi bem-sucedida e todos os arquivos foram copiados, deleta a origem
            if result["status"] != "error" and result.get("files_copied", 0) > 0:
                try:
                    source_path = Path(source)

                    # Se for arquivo, delete o arquivo
                    if source_path.is_file():
                        source_path.unlink()
                    # Se for diretório, delete recursivamente
                    else:
                        shutil.rmtree(source_path)

                    result["operation"] = "move"
                except Exception as e:
                    # Se falhar ao deletar, ainda assim retorna sucesso mas com aviso
                    result["move_error"] = f"Arquivos foram copiados mas não removidos da origem: {str(e)}"

            return result
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def derive_key_from_password(password: str, salt: bytes = None) -> tuple:
        """Deriva uma chave AES-256 a partir da senha usando PBKDF2"""
        if salt is None:
            salt = get_random_bytes(16)
        key = PBKDF2(password, salt, dkLen=32, count=100000)
        return key, salt

    @staticmethod
    def encrypt_file(input_path: str, output_path: str, password: str) -> Dict:
        """Criptografa um arquivo usando AES-256"""
        try:
            key, salt = ParallelCopyService.derive_key_from_password(password)
            cipher = AES.new(key, AES.MODE_GCM)

            with open(input_path, 'rb') as f:
                plaintext = f.read()

            ciphertext, tag = cipher.encrypt_and_digest(plaintext)

            # Salvar: salt + nonce + tag + ciphertext
            with open(output_path, 'wb') as f:
                f.write(salt)
                f.write(cipher.nonce)
                f.write(tag)
                f.write(ciphertext)

            return {"status": "success", "file": output_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def decrypt_file(input_path: str, output_path: str, password: str) -> Dict:
        """Descriptografa um arquivo criptografado com AES-256"""
        try:
            with open(input_path, 'rb') as f:
                salt = f.read(16)
                nonce = f.read(16)
                tag = f.read(16)
                ciphertext = f.read()

            key, _ = ParallelCopyService.derive_key_from_password(password, salt)
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)

            with open(output_path, 'wb') as f:
                f.write(plaintext)

            return {"status": "success", "file": output_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_statistics() -> Dict:
        """Obtém estatísticas do histórico de cópias"""
        try:
            history = ParallelCopyService.get_history()
            if not history:
                return {
                    "total_operations": 0,
                    "total_size_mb": 0,
                    "total_time_seconds": 0,
                    "average_speed_mbps": 0,
                    "successful_operations": 0,
                    "failed_operations": 0
                }

            total_ops = len(history)
            total_size = sum(op.get('size_mb', 0) for op in history)
            total_time = sum(op.get('time_seconds', 0) for op in history)
            successful = sum(1 for op in history if op.get('failed_files', 0) == 0)
            failed = total_ops - successful
            avg_speed = total_size / (total_time + 0.1) if total_time > 0 else 0

            return {
                "total_operations": total_ops,
                "total_size_mb": round(total_size, 2),
                "total_time_seconds": round(total_time, 2),
                "average_speed_mbps": round(avg_speed, 2),
                "successful_operations": successful,
                "failed_operations": failed,
                "success_rate": round((successful / total_ops * 100) if total_ops > 0 else 0, 2)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_speed_comparison() -> Dict:
        """Compara velocidades de cópias recentes"""
        try:
            history = ParallelCopyService.get_history()
            if len(history) < 2:
                return {"status": "insufficient_data"}

            recent = history[-5:] if len(history) >= 5 else history
            speeds = [op.get('speed_mbps', 0) for op in recent]

            return {
                "status": "success",
                "recent_speeds": speeds,
                "fastest": max(speeds),
                "slowest": min(speeds),
                "average": round(sum(speeds) / len(speeds), 2),
                "trend": "increasing" if speeds[-1] > speeds[0] else "decreasing"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def save_scheduled_task(task: Dict) -> Dict:
        """Salva uma tarefa agendada"""
        try:
            schedule_file = Path("schedule.json")
            tasks = []

            if schedule_file.exists():
                try:
                    with open(schedule_file, "r", encoding="utf-8") as f:
                        tasks = json.load(f)
                except (json.JSONDecodeError, IOError):
                    tasks = []

            task["id"] = str(time.time())
            task["created_at"] = datetime.now().isoformat()
            tasks.append(task)

            with open(schedule_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)

            return {"status": "success", "task_id": task["id"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_scheduled_tasks() -> list:
        """Obtém lista de tarefas agendadas"""
        schedule_file = Path("schedule.json")
        if schedule_file.exists():
            try:
                with open(schedule_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    @staticmethod
    def execute_scheduled_tasks(copy_service) -> Dict:
        """Executa tarefas agendadas pendentes"""
        tasks = ParallelCopyService.get_scheduled_tasks()
        executed = 0
        failed = 0

        for task in tasks:
            if not task.get("enabled", True):
                continue

            scheduled_time = task.get("time")
            if scheduled_time and ParallelCopyService._is_time_to_execute(scheduled_time):
                try:
                    result = copy_service.copy_with_progress_parallel(
                        task["source"],
                        task["destination"]
                    )
                    if result["status"] != "error":
                        executed += 1
                        task["last_executed"] = datetime.now().isoformat()
                    else:
                        failed += 1
                except Exception:
                    failed += 1

        # Salvar estado atualizado
        if executed > 0 or failed > 0:
            ParallelCopyService._update_scheduled_tasks(tasks)

        return {
            "status": "completed",
            "executed": executed,
            "failed": failed
        }

    @staticmethod
    def _is_time_to_execute(scheduled_time: str) -> bool:
        """Verifica se é a hora de executar a tarefa"""
        try:
            hour, minute = map(int, scheduled_time.split(":"))
            now = datetime.now()
            return now.hour == hour and now.minute == minute
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def _update_scheduled_tasks(tasks: list):
        """Atualiza o arquivo de tarefas agendadas"""
        try:
            schedule_file = Path("schedule.json")
            with open(schedule_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
