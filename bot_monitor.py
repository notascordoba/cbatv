#!/usr/bin/env python3
"""
Sistema de monitoreo para el bot de automatización periodística
Desarrollado por: MiniMax Agent
"""

import os
import time
import json
import psutil
import requests
from datetime import datetime, timedelta
import logging
from typing import Dict, List
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BotMonitor:
    """Monitor del sistema de automatización periodística"""
    
    def __init__(self):
        self.stats_file = 'logs/bot_stats.json'
        self.alerts_file = 'logs/alerts.json'
        self.last_check = datetime.now()
        
        # Configuración de alertas por email (opcional)
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.email_user = os.getenv('ALERT_EMAIL_USER')
        self.email_password = os.getenv('ALERT_EMAIL_PASSWORD')
        self.alert_recipients = os.getenv('ALERT_RECIPIENTS', '').split(',')
        
        # Umbrales de alerta
        self.cpu_threshold = 80  # %
        self.memory_threshold = 85  # %
        self.disk_threshold = 90  # %
        self.error_rate_threshold = 20  # %
        
    def get_system_stats(self) -> Dict:
        """Obtiene estadísticas del sistema"""
        try:
            stats = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'disk_free_gb': psutil.disk_usage('/').free / (1024**3),
                'uptime': time.time() - psutil.boot_time()
            }
            
            # Procesos relacionados con el bot
            bot_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                if 'telegram_to_wordpress' in proc.info['name'] or 'python' in proc.info['name']:
                    try:
                        cmdline = proc.cmdline()
                        if any('telegram_to_wordpress' in cmd for cmd in cmdline):
                            bot_processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'cpu_percent': proc.info['cpu_percent'],
                                'memory_percent': proc.info['memory_percent']
                            })
                    except:
                        continue
            
            stats['bot_processes'] = bot_processes
            stats['bot_running'] = len(bot_processes) > 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas del sistema: {e}")
            return {}
    
    def get_bot_stats(self) -> Dict:
        """Lee estadísticas del bot desde archivo de logs"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error leyendo estadísticas del bot: {e}")
            return {}
    
    def analyze_log_files(self) -> Dict:
        """Analiza archivos de log para detectar problemas"""
        try:
            log_analysis = {
                'error_count': 0,
                'warning_count': 0,
                'recent_errors': [],
                'last_activity': None
            }
            
            log_file = 'logs/bot.log'
            if os.path.exists(log_file):
                # Leer últimas 100 líneas
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-100:]
                
                cutoff_time = datetime.now() - timedelta(hours=1)
                
                for line in lines:
                    try:
                        # Extraer timestamp si está disponible
                        if ' - ' in line and (' ERROR ' in line or ' WARNING ' in line):
                            timestamp_str = line.split(' - ')[0]
                            timestamp = datetime.fromisoformat(timestamp_str.replace(',', '.'))
                            
                            if timestamp > cutoff_time:
                                if ' ERROR ' in line:
                                    log_analysis['error_count'] += 1
                                    log_analysis['recent_errors'].append(line.strip())
                                elif ' WARNING ' in line:
                                    log_analysis['warning_count'] += 1
                        
                        # Detectar última actividad
                        if 'Artículo creado exitosamente' in line:
                            timestamp_str = line.split(' - ')[0]
                            log_analysis['last_activity'] = timestamp_str
                    except:
                        continue
            
            return log_analysis
            
        except Exception as e:
            logger.error(f"Error analizando logs: {e}")
            return {}
    
    def check_external_services(self) -> Dict:
        """Verifica conectividad con servicios externos"""
        services_status = {
            'telegram_api': False,
            'groq_api': False,
            'wordpress': False,
            'internet': False
        }
        
        try:
            # Test de conectividad a internet
            response = requests.get('https://8.8.8.8', timeout=5)
            services_status['internet'] = True
        except:
            services_status['internet'] = False
        
        try:
            # Test API de Telegram
            response = requests.get('https://api.telegram.org', timeout=10)
            services_status['telegram_api'] = response.status_code == 200
        except:
            pass
        
        try:
            # Test API de Groq
            response = requests.get('https://api.groq.com', timeout=10)
            services_status['groq_api'] = response.status_code in [200, 404]  # 404 es normal sin auth
        except:
            pass
        
        # WordPress test (requeriría configuración específica)
        wordpress_url = os.getenv('WORDPRESS_URL')
        if wordpress_url:
            try:
                base_url = wordpress_url.replace('/xmlrpc.php', '')
                response = requests.get(base_url, timeout=10)
                services_status['wordpress'] = response.status_code == 200
            except:
                pass
        
        return services_status
    
    def generate_alert(self, alert_type: str, message: str, severity: str = 'warning'):
        """Genera alerta y la envía por email si está configurado"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'message': message,
            'severity': severity
        }
        
        # Guardar alerta en archivo
        alerts = []
        if os.path.exists(self.alerts_file):
            with open(self.alerts_file, 'r') as f:
                alerts = json.load(f)
        
        alerts.append(alert)
        
        # Mantener solo las últimas 50 alertas
        alerts = alerts[-50:]
        
        with open(self.alerts_file, 'w') as f:
            json.dump(alerts, f, indent=2)
        
        # Log de la alerta
        log_level = logging.ERROR if severity == 'critical' else logging.WARNING
        logger.log(log_level, f"ALERTA {alert_type}: {message}")
        
        # Enviar email si está configurado y es crítico
        if severity == 'critical' and self.email_user and self.alert_recipients:
            self.send_email_alert(alert)
    
    def send_email_alert(self, alert: Dict):
        """Envía alerta por email"""
        try:
            msg = MimeMultipart()
            msg['From'] = self.email_user
            msg['To'] = ', '.join(self.alert_recipients)
            msg['Subject'] = f"🚨 ALERTA CRÍTICA: Bot Periodístico - {alert['type']}"
            
            body = f"""
ALERTA DEL SISTEMA DE AUTOMATIZACIÓN PERIODÍSTICA

Tipo: {alert['type']}
Severidad: {alert['severity']}
Hora: {alert['timestamp']}

Mensaje:
{alert['message']}

---
Sistema de Monitoreo Automático
            """
            
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            text = msg.as_string()
            server.sendmail(self.email_user, self.alert_recipients, text)
            server.quit()
            
            logger.info("Alerta enviada por email exitosamente")
            
        except Exception as e:
            logger.error(f"Error enviando alerta por email: {e}")
    
    def run_health_check(self) -> Dict:
        """Ejecuta chequeo completo de salud del sistema"""
        logger.info("Iniciando chequeo de salud del sistema...")
        
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'issues': []
        }
        
        # Chequeo del sistema
        system_stats = self.get_system_stats()
        if system_stats:
            health_report['system'] = system_stats
            
            # Alertas de recursos
            if system_stats['cpu_percent'] > self.cpu_threshold:
                issue = f"Alto uso de CPU: {system_stats['cpu_percent']:.1f}%"
                health_report['issues'].append(issue)
                self.generate_alert('high_cpu', issue, 'warning')
            
            if system_stats['memory_percent'] > self.memory_threshold:
                issue = f"Alto uso de memoria: {system_stats['memory_percent']:.1f}%"
                health_report['issues'].append(issue)
                self.generate_alert('high_memory', issue, 'warning')
            
            if system_stats['disk_percent'] > self.disk_threshold:
                issue = f"Poco espacio en disco: {system_stats['disk_percent']:.1f}%"
                health_report['issues'].append(issue)
                self.generate_alert('low_disk', issue, 'critical')
            
            # Verificar si el bot está ejecutándose
            if not system_stats['bot_running']:
                issue = "Bot no está ejecutándose"
                health_report['issues'].append(issue)
                self.generate_alert('bot_down', issue, 'critical')
        
        # Análisis de logs
        log_analysis = self.analyze_log_files()
        if log_analysis:
            health_report['logs'] = log_analysis
            
            # Alertas por errores frecuentes
            if log_analysis['error_count'] > 5:
                issue = f"Muchos errores recientes: {log_analysis['error_count']}"
                health_report['issues'].append(issue)
                self.generate_alert('frequent_errors', issue, 'warning')
        
        # Chequeo de servicios externos
        services = self.check_external_services()
        health_report['external_services'] = services
        
        failed_services = [service for service, status in services.items() if not status]
        if failed_services:
            issue = f"Servicios no disponibles: {', '.join(failed_services)}"
            health_report['issues'].append(issue)
            severity = 'critical' if 'internet' in failed_services else 'warning'
            self.generate_alert('service_down', issue, severity)
        
        # Estadísticas del bot
        bot_stats = self.get_bot_stats()
        if bot_stats:
            health_report['bot_stats'] = bot_stats
        
        # Determinar estado general
        if any('critical' in str(issue) for issue in health_report['issues']):
            health_report['overall_status'] = 'critical'
        elif health_report['issues']:
            health_report['overall_status'] = 'warning'
        
        # Guardar reporte
        with open('logs/health_report.json', 'w') as f:
            json.dump(health_report, f, indent=2)
        
        logger.info(f"Chequeo completado. Estado: {health_report['overall_status']}")
        
        return health_report
    
    def generate_daily_report(self):
        """Genera reporte diario del sistema"""
        try:
            report = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'summary': {},
                'performance': {},
                'alerts': []
            }
            
            # Leer alertas del día
            if os.path.exists(self.alerts_file):
                with open(self.alerts_file, 'r') as f:
                    alerts = json.load(f)
                
                today = datetime.now().date()
                today_alerts = [
                    alert for alert in alerts
                    if datetime.fromisoformat(alert['timestamp']).date() == today
                ]
                report['alerts'] = today_alerts
            
            # Estadísticas del bot
            bot_stats = self.get_bot_stats()
            if bot_stats:
                report['bot_performance'] = bot_stats
            
            # Guardar reporte diario
            daily_report_file = f"logs/daily_report_{report['date']}.json"
            with open(daily_report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Reporte diario generado: {daily_report_file}")
            
        except Exception as e:
            logger.error(f"Error generando reporte diario: {e}")
    
    def start_monitoring(self, interval_minutes: int = 5):
        """Inicia monitoreo continuo"""
        logger.info(f"Iniciando monitoreo continuo cada {interval_minutes} minutos")
        
        last_daily_report = datetime.now().date()
        
        try:
            while True:
                # Chequeo de salud
                health_report = self.run_health_check()
                
                # Generar reporte diario si es nuevo día
                if datetime.now().date() > last_daily_report:
                    self.generate_daily_report()
                    last_daily_report = datetime.now().date()
                
                # Esperar próximo chequeo
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            logger.info("Monitoreo detenido por el usuario")
        except Exception as e:
            logger.error(f"Error en monitoreo: {e}")


def main():
    """Función principal del monitor"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor del Sistema de Automatización Periodística')
    parser.add_argument('--interval', type=int, default=5, help='Intervalo de monitoreo en minutos')
    parser.add_argument('--single-check', action='store_true', help='Ejecutar un solo chequeo')
    parser.add_argument('--daily-report', action='store_true', help='Generar reporte diario')
    
    args = parser.parse_args()
    
    # Crear directorio de logs
    os.makedirs('logs', exist_ok=True)
    
    monitor = BotMonitor()
    
    if args.single_check:
        health_report = monitor.run_health_check()
        print(json.dumps(health_report, indent=2))
    elif args.daily_report:
        monitor.generate_daily_report()
    else:
        monitor.start_monitoring(args.interval)


if __name__ == "__main__":
    main()