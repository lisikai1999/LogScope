import os
import re
import json
import subprocess
import asyncio
import shutil
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from logger import app_logger


@dataclass
class TrivyVulnerability:
    vulnerability_id: Optional[str] = None
    cve_id: Optional[str] = None
    ghsa_id: Optional[str] = None
    severity: str = "unknown"
    title: Optional[str] = None
    description: Optional[str] = None
    package_name: Optional[str] = None
    installed_version: Optional[str] = None
    fixed_version: Optional[str] = None
    package_type: Optional[str] = None
    cvss_score: Optional[str] = None
    cvss_vector: Optional[str] = None
    primary_url: Optional[str] = None
    references: List[str] = field(default_factory=list)
    published_date: Optional[datetime] = None
    last_modified_date: Optional[datetime] = None


@dataclass
class TrivySecret:
    secret_type: str = "unknown"
    filename: Optional[str] = None
    layer: Optional[str] = None
    match: Optional[str] = None
    match_start_index: int = 0
    match_end_index: int = 0
    severity: str = "high"
    category: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TrivyConfigIssue:
    check_type: str = "config"
    check_id: Optional[str] = None
    severity: str = "medium"
    category: Optional[str] = None
    message: Optional[str] = None
    description: Optional[str] = None
    remediation: Optional[str] = None
    location: Dict[str, Any] = field(default_factory=dict)
    references: List[str] = field(default_factory=list)


@dataclass
class TrivyScanResult:
    image_name: str
    image_id: Optional[str] = None
    
    vulnerabilities: List[TrivyVulnerability] = field(default_factory=list)
    secrets: List[TrivySecret] = field(default_factory=list)
    config_issues: List[TrivyConfigIssue] = field(default_factory=list)
    
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    unknown_count: int = 0
    secret_count: int = 0
    config_issue_count: int = 0
    
    raw_result: Optional[Dict[str, Any]] = None
    scan_report: Optional[str] = None
    
    def count_vulnerabilities(self):
        self.critical_count = sum(1 for v in self.vulnerabilities if v.severity.lower() == "critical")
        self.high_count = sum(1 for v in self.vulnerabilities if v.severity.lower() == "high")
        self.medium_count = sum(1 for v in self.vulnerabilities if v.severity.lower() == "medium")
        self.low_count = sum(1 for v in self.vulnerabilities if v.severity.lower() == "low")
        self.unknown_count = sum(1 for v in self.vulnerabilities if v.severity.lower() == "unknown")
        self.secret_count = len(self.secrets)
        self.config_issue_count = len(self.config_issues)


class TrivyService:
    def __init__(self):
        self._trivy_available = self._check_trivy_available()
        self._trivy_path = self._find_trivy_path()
    
    def _check_trivy_available(self) -> bool:
        """检查 Trivy 是否可用"""
        trivy_path = shutil.which('trivy')
        if trivy_path:
            try:
                result = subprocess.run(
                    [trivy_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    app_logger.info(f"[TrivyService] Trivy 可用: {result.stdout.strip()}")
                    return True
            except Exception as e:
                app_logger.warning(f"[TrivyService] Trivy 检查失败: {e}")
        app_logger.warning("[TrivyService] Trivy 不可用，将使用模拟模式")
        return False
    
    def _find_trivy_path(self) -> str:
        """查找 Trivy 可执行文件路径"""
        trivy_path = shutil.which('trivy')
        if trivy_path:
            return trivy_path
        
        common_paths = [
            '/usr/local/bin/trivy',
            '/usr/bin/trivy',
            '/opt/homebrew/bin/trivy',
        ]
        
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        
        return 'trivy'
    
    def is_available(self) -> bool:
        return self._trivy_available
    
    def scan_image(
        self,
        image_name: str,
        scan_type: str = "all",
        timeout: int = 300,
        format: str = "json",
        registry_auth: Optional[Dict[str, Any]] = None
    ) -> TrivyScanResult:
        """
        扫描镜像
        
        参数:
            image_name: 镜像名称，如 nginx:latest
            scan_type: 扫描类型: vulnerability, secret, config, all
            timeout: 超时时间（秒）
            format: 输出格式
            registry_auth: 仓库认证信息
        
        返回:
            TrivyScanResult 对象
        """
        if not self._trivy_available:
            app_logger.info(f"[TrivyService] Trivy 不可用，使用模拟扫描: {image_name}")
            return self._mock_scan_image(image_name, scan_type)
        
        try:
            app_logger.info(f"[TrivyService] 开始扫描镜像: {image_name}, 类型: {scan_type}")
            
            result = TrivyScanResult(image_name=image_name)
            
            scanners = []
            if scan_type == "all" or scan_type == "vulnerability":
                scanners.append("vuln")
            if scan_type == "all" or scan_type == "secret":
                scanners.append("secret")
            if scan_type == "all" or scan_type == "config":
                scanners.append("config")
            
            cmd = [
                self._trivy_path,
                "image",
                "--scanners", ",".join(scanners),
                "--format", "json",
                "-o", "-",
                image_name
            ]
            
            env = os.environ.copy()
            if registry_auth:
                if registry_auth.get('username') and registry_auth.get('password'):
                    env['TRIVY_USERNAME'] = registry_auth['username']
                    env['TRIVY_PASSWORD'] = registry_auth['password']
            
            app_logger.debug(f"[TrivyService] 执行命令: {' '.join(cmd)}")
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            if process.returncode != 0:
                app_logger.error(f"[TrivyService] 扫描失败: {process.stderr}")
                raise Exception(f"Trivy 扫描失败: {process.stderr}")
            
            try:
                raw_result = json.loads(process.stdout)
                result.raw_result = raw_result
                
                self._parse_trivy_result(result, raw_result)
                result.count_vulnerabilities()
                
                app_logger.info(
                    f"[TrivyService] 扫描完成: {image_name}, "
                    f"漏洞数: {result.critical_count + result.high_count + result.medium_count + result.low_count}, "
                    f"敏感信息: {result.secret_count}, "
                    f"配置问题: {result.config_issue_count}"
                )
                
                return result
                
            except json.JSONDecodeError as e:
                app_logger.error(f"[TrivyService] 解析扫描结果失败: {e}")
                app_logger.error(f"[TrivyService] 原始输出: {process.stdout[:500]}")
                raise Exception(f"解析扫描结果失败: {e}")
                
        except subprocess.TimeoutExpired:
            app_logger.error(f"[TrivyService] 扫描超时: {image_name}")
            raise Exception(f"扫描超时（{timeout}秒）")
        except Exception as e:
            app_logger.error(f"[TrivyService] 扫描失败: {e}")
            raise
    
    def _parse_trivy_result(self, result: TrivyScanResult, raw_result: Dict[str, Any]):
        """解析 Trivy 扫描结果"""
        results = raw_result.get('Results', [])
        
        for item in results:
            target = item.get('Target', '')
            class_type = item.get('Class', '')
            type_info = item.get('Type', '')
            
            vulnerabilities = item.get('Vulnerabilities', [])
            secrets = item.get('Secrets', [])
            misconfigurations = item.get('Misconfigurations', [])
            
            for vuln in vulnerabilities:
                trivy_vuln = TrivyVulnerability()
                
                trivy_vuln.vulnerability_id = vuln.get('VulnerabilityID')
                trivy_vuln.cve_id = vuln.get('VulnerabilityID')
                trivy_vuln.title = vuln.get('Title')
                trivy_vuln.description = vuln.get('Description')
                trivy_vuln.severity = vuln.get('Severity', 'UNKNOWN').lower()
                trivy_vuln.package_name = vuln.get('PkgName')
                trivy_vuln.installed_version = vuln.get('InstalledVersion')
                trivy_vuln.fixed_version = vuln.get('FixedVersion')
                trivy_vuln.package_type = type_info
                
                cvss_data = vuln.get('CVSS', {})
                if cvss_data:
                    for cvss_source, cvss_info in cvss_data.items():
                        if cvss_info.get('V3Score'):
                            trivy_vuln.cvss_score = str(cvss_info['V3Score'])
                            trivy_vuln.cvss_vector = cvss_info.get('V3Vector')
                            break
                
                trivy_vuln.primary_url = vuln.get('PrimaryURL')
                trivy_vuln.references = vuln.get('References', [])
                
                result.vulnerabilities.append(trivy_vuln)
            
            for secret in secrets:
                trivy_secret = TrivySecret()
                
                trivy_secret.secret_type = secret.get('RuleID', 'unknown')
                trivy_secret.filename = secret.get('FilePath')
                trivy_secret.layer = secret.get('Layer')
                trivy_secret.match = secret.get('Match')
                trivy_secret.severity = secret.get('Severity', 'high').lower()
                trivy_secret.category = secret.get('Category')
                trivy_secret.description = secret.get('Description')
                
                result.secrets.append(trivy_secret)
            
            for misconfig in misconfigurations:
                trivy_config = TrivyConfigIssue()
                
                trivy_config.check_id = misconfig.get('ID')
                trivy_config.check_type = 'config'
                trivy_config.title = misconfig.get('Title')
                trivy_config.description = misconfig.get('Description')
                trivy_config.severity = misconfig.get('Severity', 'medium').lower()
                trivy_config.message = misconfig.get('Message')
                trivy_config.remediation = misconfig.get('Resolution')
                trivy_config.references = misconfig.get('References', [])
                
                trivy_config.location = {
                    'filename': misconfig.get('Filename'),
                    'start_line': misconfig.get('StartLine'),
                    'end_line': misconfig.get('EndLine'),
                }
                
                result.config_issues.append(trivy_config)
    
    def _mock_scan_image(self, image_name: str, scan_type: str) -> TrivyScanResult:
        """模拟扫描结果（用于演示）"""
        result = TrivyScanResult(image_name=image_name)
        
        mock_vulnerabilities = [
            {
                'vulnerability_id': 'CVE-2024-0001',
                'cve_id': 'CVE-2024-0001',
                'severity': 'critical',
                'title': 'Critical Remote Code Execution Vulnerability',
                'description': 'A critical vulnerability that allows remote code execution...',
                'package_name': 'openssl',
                'installed_version': '1.1.1k',
                'fixed_version': '1.1.1t',
                'package_type': 'os',
                'cvss_score': '9.8',
                'cvss_vector': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
                'primary_url': 'https://nvd.nist.gov/vuln/detail/CVE-2024-0001',
                'references': [
                    'https://example.com/advisory-1',
                    'https://example.com/fix-info'
                ]
            },
            {
                'vulnerability_id': 'CVE-2024-0002',
                'cve_id': 'CVE-2024-0002',
                'severity': 'high',
                'title': 'High Privilege Escalation Vulnerability',
                'description': 'A high-severity vulnerability that allows privilege escalation...',
                'package_name': 'sudo',
                'installed_version': '1.9.5',
                'fixed_version': '1.9.5p2',
                'package_type': 'os',
                'cvss_score': '7.8',
                'cvss_vector': 'CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H',
                'primary_url': 'https://nvd.nist.gov/vuln/detail/CVE-2024-0002',
                'references': []
            },
            {
                'vulnerability_id': 'CVE-2024-0003',
                'cve_id': 'CVE-2024-0003',
                'severity': 'medium',
                'title': 'Medium Information Disclosure Vulnerability',
                'description': 'A medium-severity vulnerability that allows information disclosure...',
                'package_name': 'curl',
                'installed_version': '7.74.0',
                'fixed_version': '7.74.0-1.3+deb11u3',
                'package_type': 'os',
                'cvss_score': '5.3',
                'cvss_vector': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N',
                'primary_url': 'https://nvd.nist.gov/vuln/detail/CVE-2024-0003',
                'references': []
            },
            {
                'vulnerability_id': 'CVE-2024-0004',
                'cve_id': 'CVE-2024-0004',
                'severity': 'low',
                'title': 'Low Denial of Service Vulnerability',
                'description': 'A low-severity vulnerability that may cause denial of service...',
                'package_name': 'glibc',
                'installed_version': '2.31',
                'fixed_version': '2.31-13+deb11u5',
                'package_type': 'os',
                'cvss_score': '3.7',
                'cvss_vector': 'CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:N/A:L',
                'primary_url': 'https://nvd.nist.gov/vuln/detail/CVE-2024-0004',
                'references': []
            }
        ]
        
        mock_secrets = [
            {
                'secret_type': 'aws-access-key-id',
                'filename': '/root/.aws/credentials',
                'severity': 'critical',
                'category': 'credentials',
                'description': 'AWS Access Key ID found in credentials file',
                'match': 'AKIAIOSFODNN7EXAMPLE'
            },
            {
                'secret_type': 'private-key',
                'filename': '/etc/ssh/ssh_host_rsa_key',
                'severity': 'critical',
                'category': 'cryptographic',
                'description': 'Private SSH key found in image',
                'match': '-----BEGIN RSA PRIVATE KEY-----'
            }
        ]
        
        mock_config_issues = [
            {
                'check_id': 'DS002',
                'severity': 'high',
                'category': 'Security',
                'title': 'Image should not run with root user',
                'message': 'Last user in Dockerfile is root',
                'description': 'Running containers with root user can lead to privilege escalation',
                'remediation': 'Use USER instruction to switch to a non-root user',
                'references': ['https://docs.docker.com/develop/develop-images/dockerfile_best-practices/'],
                'location': {
                    'filename': 'Dockerfile',
                    'start_line': 1,
                    'end_line': 10
                }
            },
            {
                'check_id': 'DS006',
                'severity': 'medium',
                'category': 'Secret',
                'title': 'ENV variable should not contain secrets',
                'message': 'Potential secret found in environment variable',
                'description': 'Sensitive data should not be stored in environment variables',
                'remediation': 'Use secrets management solutions or build arguments',
                'references': [],
                'location': {
                    'filename': 'Dockerfile',
                    'start_line': 5,
                    'end_line': 5
                }
            },
            {
                'check_id': 'DS015',
                'severity': 'low',
                'category': 'Best Practice',
                'title': 'Image should have a healthcheck',
                'message': 'No HEALTHCHECK instruction found',
                'description': 'Healthchecks help Docker determine if a container is healthy',
                'remediation': 'Add HEALTHCHECK instruction to the Dockerfile',
                'references': [],
                'location': {
                    'filename': 'Dockerfile',
                    'start_line': 0,
                    'end_line': 0
                }
            }
        ]
        
        if scan_type == "all" or scan_type == "vulnerability":
            for vuln_data in mock_vulnerabilities:
                vuln = TrivyVulnerability(
                    vulnerability_id=vuln_data['vulnerability_id'],
                    cve_id=vuln_data['cve_id'],
                    severity=vuln_data['severity'],
                    title=vuln_data['title'],
                    description=vuln_data['description'],
                    package_name=vuln_data['package_name'],
                    installed_version=vuln_data['installed_version'],
                    fixed_version=vuln_data['fixed_version'],
                    package_type=vuln_data['package_type'],
                    cvss_score=vuln_data['cvss_score'],
                    cvss_vector=vuln_data['cvss_vector'],
                    primary_url=vuln_data['primary_url'],
                    references=vuln_data['references']
                )
                result.vulnerabilities.append(vuln)
        
        if scan_type == "all" or scan_type == "secret":
            for secret_data in mock_secrets:
                secret = TrivySecret(
                    secret_type=secret_data['secret_type'],
                    filename=secret_data['filename'],
                    severity=secret_data['severity'],
                    category=secret_data['category'],
                    description=secret_data['description'],
                    match=secret_data['match']
                )
                result.secrets.append(secret)
        
        if scan_type == "all" or scan_type == "config":
            for config_data in mock_config_issues:
                config = TrivyConfigIssue(
                    check_id=config_data['check_id'],
                    severity=config_data['severity'],
                    category=config_data['category'],
                    message=config_data['message'],
                    description=config_data['description'],
                    remediation=config_data['remediation'],
                    references=config_data['references'],
                    location=config_data['location']
                )
                result.config_issues.append(config)
        
        result.count_vulnerabilities()
        result.raw_result = {
            'mock': True,
            'image': image_name,
            'scan_type': scan_type
        }
        
        return result
    
    def scan_filesystem(
        self,
        path: str,
        scan_type: str = "all",
        timeout: int = 300
    ) -> TrivyScanResult:
        """
        扫描文件系统
        
        参数:
            path: 文件系统路径
            scan_type: 扫描类型
            timeout: 超时时间
        
        返回:
            TrivyScanResult 对象
        """
        if not self._trivy_available:
            app_logger.info(f"[TrivyService] Trivy 不可用，使用模拟扫描: {path}")
            return self._mock_scan_image(path, scan_type)
        
        raise NotImplementedError("文件系统扫描暂未实现")
    
    def scan_config(
        self,
        path: str,
        timeout: int = 300
    ) -> TrivyScanResult:
        """
        扫描配置文件（IaC 等）
        
        参数:
            path: 配置文件路径
            timeout: 超时时间
        
        返回:
            TrivyScanResult 对象
        """
        if not self._trivy_available:
            app_logger.info(f"[TrivyService] Trivy 不可用，使用模拟扫描: {path}")
            return self._mock_scan_image(path, "config")
        
        raise NotImplementedError("配置文件扫描暂未实现")
    
    def get_version(self) -> Optional[str]:
        """获取 Trivy 版本"""
        if not self._trivy_available:
            return None
        
        try:
            result = subprocess.run(
                [self._trivy_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            app_logger.error(f"[TrivyService] 获取版本失败: {e}")
        
        return None
    
    def update_database(self) -> bool:
        """更新漏洞数据库"""
        if not self._trivy_available:
            return False
        
        try:
            app_logger.info("[TrivyService] 更新漏洞数据库...")
            result = subprocess.run(
                [self._trivy_path, 'image', '--download-db-only', 'scratch'],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                app_logger.info("[TrivyService] 漏洞数据库更新成功")
                return True
            else:
                app_logger.error(f"[TrivyService] 漏洞数据库更新失败: {result.stderr}")
                return False
        except Exception as e:
            app_logger.error(f"[TrivyService] 漏洞数据库更新失败: {e}")
            return False


trivy_service = TrivyService()
