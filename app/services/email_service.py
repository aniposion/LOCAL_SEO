"""Email service using SendGrid."""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailUnavailableError(RuntimeError):
    """Raised when SendGrid is not configured or installed."""


class EmailDeliveryError(RuntimeError):
    """Raised when SendGrid fails to send a message."""


class EmailService:
    """Service for sending emails via SendGrid.
    
    Used for:
    - Review request emails (P2)
    - Weekly report delivery (P1)
    - Notifications
    """

    def __init__(self):
        self.api_key = settings.sendgrid_api_key
        self.default_from = settings.sendgrid_from_email
        self._client = None

    @property
    def client(self):
        """Lazy load SendGrid client."""
        if self._client is None:
            if not self.api_key:
                raise EmailUnavailableError("SendGrid API key is not configured")

            try:
                from sendgrid import SendGridAPIClient
            except ImportError as exc:
                raise EmailUnavailableError("SendGrid SDK is not installed") from exc

            try:
                self._client = SendGridAPIClient(self.api_key)
            except Exception as exc:
                raise EmailUnavailableError(f"Failed to initialize SendGrid client: {exc}") from exc
        return self._client

    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: list = None,
    ) -> dict:
        """Send an email.
        
        Args:
            to: Recipient email
            subject: Email subject
            html_content: HTML body
            from_email: Sender email (defaults to configured)
            from_name: Sender name
            reply_to: Reply-to address
            attachments: List of attachment dicts
            
        Returns:
            dict with message_id, status
        """
        from_email = from_email or self.default_from
        
        if not from_email:
            raise EmailUnavailableError("SendGrid sender email is not configured")
        
        try:
            from sendgrid.helpers.mail import (
                Mail, Email, To, Content, Attachment, 
                FileContent, FileName, FileType, Disposition
            )
            
            message = Mail(
                from_email=Email(from_email, from_name),
                to_emails=To(to),
                subject=subject,
                html_content=Content("text/html", html_content),
            )
            
            if reply_to:
                from sendgrid.helpers.mail import ReplyTo
                message.reply_to = ReplyTo(reply_to)
            
            # Add attachments
            if attachments:
                for att in attachments:
                    attachment = Attachment(
                        FileContent(att['content']),
                        FileName(att['filename']),
                        FileType(att.get('type', 'application/pdf')),
                        Disposition('attachment'),
                    )
                    message.add_attachment(attachment)
            
            response = self.client.send(message)
            
            logger.info(f"Email sent to {to}, status: {response.status_code}")
            
            return {
                "message_id": response.headers.get('X-Message-Id'),
                "status_code": response.status_code,
                "to": to,
            }
            
        except EmailUnavailableError:
            raise
        except ImportError as exc:
            raise EmailUnavailableError(f"SendGrid helpers are unavailable: {exc}") from exc
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise EmailDeliveryError(str(e)) from e

    async def send_template_email(
        self,
        to: str,
        template_id: str,
        dynamic_data: dict,
        from_email: Optional[str] = None,
    ) -> dict:
        """Send email using SendGrid dynamic template."""
        from_email = from_email or self.default_from
        
        try:
            from sendgrid.helpers.mail import Mail, Email, To
            
            message = Mail(
                from_email=Email(from_email),
                to_emails=To(to),
            )
            message.template_id = template_id
            message.dynamic_template_data = dynamic_data
            
            response = self.client.send(message)
            
            return {
                "message_id": response.headers.get('X-Message-Id'),
                "status_code": response.status_code,
            }
        except EmailUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Failed to send template email: {e}")
            raise EmailDeliveryError(str(e)) from e

    async def send_weekly_report(
        self,
        to: str,
        report_data: dict,
        pdf_content: Optional[bytes] = None,
    ) -> dict:
        """Send weekly report email with optional PDF attachment."""
        subject = f"주간 성과 리포트 - {report_data.get('week_range', '')}"
        
        html_content = self._build_report_email(report_data)
        
        attachments = []
        if pdf_content:
            import base64
            attachments.append({
                "content": base64.b64encode(pdf_content).decode(),
                "filename": f"weekly_report_{report_data.get('week_start', 'report')}.pdf",
                "type": "application/pdf",
            })
        
        return await self.send_email(
            to=to,
            subject=subject,
            html_content=html_content,
            attachments=attachments,
        )

    async def send_payment_receipt(
        self,
        to: str,
        payment_data: dict,
    ) -> dict:
        """Send payment receipt/invoice email after successful payment.
        
        Args:
            to: Recipient email
            payment_data: Dict containing:
                - customer_name: Customer's name
                - amount: Payment amount (float)
                - currency: Currency code (e.g. 'USD', 'KRW')
                - plan_name: Subscription plan name
                - billing_cycle: 'monthly' or 'yearly'
                - invoice_url: Stripe hosted invoice URL
                - receipt_url: Stripe receipt URL (optional)
                - payment_date: Payment datetime
                - invoice_number: Invoice ID/number
                - next_billing_date: Next billing date (optional)
                
        Returns:
            dict with message_id, status
        """
        customer_name = payment_data.get('customer_name', 'Customer')
        amount = payment_data.get('amount', 0)
        currency = payment_data.get('currency', 'USD')
        plan_name = payment_data.get('plan_name', 'Subscription')
        invoice_url = payment_data.get('invoice_url', '')
        receipt_url = payment_data.get('receipt_url', '')
        payment_date = payment_data.get('payment_date', '')
        invoice_number = payment_data.get('invoice_number', '')
        billing_cycle = payment_data.get('billing_cycle', 'monthly')
        next_billing_date = payment_data.get('next_billing_date', '')
        
        # Format currency
        if currency.upper() == 'KRW':
            amount_formatted = f"₩{amount:,.0f}"
        elif currency.upper() == 'USD':
            amount_formatted = f"${amount:,.2f}"
        else:
            amount_formatted = f"{currency} {amount:,.2f}"
        
        subject = f"결제 완료 - {plan_name} 플랜 ({amount_formatted})"
        
        html_content = self._build_payment_receipt_email(
            customer_name=customer_name,
            amount_formatted=amount_formatted,
            plan_name=plan_name,
            billing_cycle=billing_cycle,
            invoice_url=invoice_url,
            receipt_url=receipt_url,
            payment_date=payment_date,
            invoice_number=invoice_number,
            next_billing_date=next_billing_date,
        )
        
        return await self.send_email(
            to=to,
            subject=subject,
            html_content=html_content,
            from_name="Local SEO Optimizer",
        )

    def _build_payment_receipt_email(
        self,
        customer_name: str,
        amount_formatted: str,
        plan_name: str,
        billing_cycle: str,
        invoice_url: str,
        receipt_url: str,
        payment_date: str,
        invoice_number: str,
        next_billing_date: str,
    ) -> str:
        """Build payment receipt email HTML."""
        billing_cycle_kr = "월간" if billing_cycle == "monthly" else "연간"
        
        # Build action buttons
        buttons_html = ""
        if invoice_url:
            buttons_html += f'''
                <a href="{invoice_url}" 
                   style="display: inline-block; background: #6366f1; color: white; 
                          padding: 12px 24px; border-radius: 8px; text-decoration: none; 
                          margin-right: 10px; margin-bottom: 10px;">
                    📄 청구서 보기
                </a>
            '''
        if receipt_url:
            buttons_html += f'''
                <a href="{receipt_url}" 
                   style="display: inline-block; background: #22c55e; color: white; 
                          padding: 12px 24px; border-radius: 8px; text-decoration: none;
                          margin-bottom: 10px;">
                    🧾 영수증 보기
                </a>
            '''
        
        next_billing_html = ""
        if next_billing_date:
            next_billing_html = f'''
                <tr>
                    <td style="padding: 12px 0; color: #666;">다음 결제일</td>
                    <td style="padding: 12px 0; text-align: right; font-weight: 500;">{next_billing_date}</td>
                </tr>
            '''
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans KR', sans-serif; 
                     padding: 20px; background: #f3f4f6; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #22c55e, #16a34a); padding: 40px 30px; text-align: center;">
                    <div style="font-size: 48px; margin-bottom: 10px;">✅</div>
                    <h1 style="margin: 0; color: white; font-size: 24px;">결제가 완료되었습니다</h1>
                    <p style="margin: 10px 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                        {customer_name}님, 감사합니다!
                    </p>
                </div>
                
                <!-- Content -->
                <div style="padding: 30px;">
                    
                    <!-- Amount Box -->
                    <div style="background: #f9fafb; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 24px;">
                        <div style="color: #666; font-size: 14px; margin-bottom: 8px;">결제 금액</div>
                        <div style="font-size: 36px; font-weight: bold; color: #1f2937;">{amount_formatted}</div>
                    </div>
                    
                    <!-- Details Table -->
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
                        <tr style="border-bottom: 1px solid #e5e7eb;">
                            <td style="padding: 12px 0; color: #666;">플랜</td>
                            <td style="padding: 12px 0; text-align: right; font-weight: 500;">{plan_name} ({billing_cycle_kr})</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #e5e7eb;">
                            <td style="padding: 12px 0; color: #666;">결제일</td>
                            <td style="padding: 12px 0; text-align: right; font-weight: 500;">{payment_date}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #e5e7eb;">
                            <td style="padding: 12px 0; color: #666;">청구서 번호</td>
                            <td style="padding: 12px 0; text-align: right; font-weight: 500; font-family: monospace;">{invoice_number}</td>
                        </tr>
                        {next_billing_html}
                    </table>
                    
                    <!-- Action Buttons -->
                    <div style="text-align: center; margin: 30px 0;">
                        {buttons_html}
                    </div>
                    
                    <!-- Info Box -->
                    <div style="background: #eff6ff; border-radius: 8px; padding: 16px; margin-top: 20px;">
                        <p style="margin: 0; color: #1e40af; font-size: 14px;">
                            💡 청구서와 영수증은 위 버튼을 클릭하여 다운로드하거나 인쇄할 수 있습니다.
                            세금계산서가 필요하신 경우 고객센터로 문의해주세요.
                        </p>
                    </div>
                </div>
                
                <!-- Footer -->
                <div style="background: #f9fafb; padding: 20px 30px; text-align: center; border-top: 1px solid #e5e7eb;">
                    <p style="margin: 0; color: #666; font-size: 12px;">
                        이 이메일은 Local SEO Optimizer 결제 시스템에서 자동으로 발송되었습니다.
                    </p>
                    <p style="margin: 8px 0 0; color: #999; font-size: 11px;">
                        문의: support@localseo.app
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    def _build_report_email(self, data: dict) -> str:
        """Build weekly report email HTML."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 30px; border-radius: 12px; text-align: center; color: white;">
                    <h1 style="margin: 0;">📊 주간 성과 리포트</h1>
                    <p style="margin: 10px 0 0;">{data.get('week_range', '')}</p>
                </div>
                
                <div style="padding: 30px; background: #f9fafb; margin-top: 20px; border-radius: 12px;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                        <div style="background: white; padding: 20px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 32px; font-weight: bold; color: #22c55e;">
                                {data.get('calls_total', 0)}
                            </div>
                            <div style="color: #666;">전화 문의</div>
                            <div style="font-size: 14px; color: {'#22c55e' if data.get('calls_delta', 0) >= 0 else '#ef4444'};">
                                {'+' if data.get('calls_delta', 0) >= 0 else ''}{data.get('calls_delta', 0)}건
                            </div>
                        </div>
                        
                        <div style="background: white; padding: 20px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 32px; font-weight: bold; color: #3b82f6;">
                                {data.get('directions_total', 0)}
                            </div>
                            <div style="color: #666;">길찾기 요청</div>
                            <div style="font-size: 14px; color: {'#22c55e' if data.get('directions_delta', 0) >= 0 else '#ef4444'};">
                                {'+' if data.get('directions_delta', 0) >= 0 else ''}{data.get('directions_delta', 0)}건
                            </div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 20px; background: white; padding: 20px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 28px; font-weight: bold; color: #6366f1;">
                            ₩{data.get('estimated_revenue', 0):,}
                        </div>
                        <div style="color: #666;">예상 매출 기여</div>
                    </div>
                </div>
                
                <p style="text-align: center; margin-top: 30px; color: #666; font-size: 14px;">
                    자세한 내용은 대시보드에서 확인하세요
                </p>
            </div>
        </body>
        </html>
        """
# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
