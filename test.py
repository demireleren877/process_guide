import win32com.client

def get_latest_email():
    try:
        # Outlook uygulamasını başlat
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")

        # Gelen Kutusunu seç
        inbox = namespace.GetDefaultFolder(6)  # 6, Gelen Kutusunun (Inbox) ID'sidir.
        messages = inbox.Items

        # E-postaları tarihe göre sırala (En yeniyi en üste al)
        messages.Sort("[ReceivedTime]", True)

        # En son gelen e-postayı al
        latest_email = messages.GetFirst()

        # E-posta bilgilerini yazdır
        print("Gönderen:", latest_email.SenderName)
        print("Konu:", latest_email.Subject)
        print("Gönderilme Zamanı:", latest_email.ReceivedTime)
        print("\nİçerik:\n", latest_email.Body)

    except Exception as e:
        print("Hata:", e)

if __name__ == "__main__":
    get_latest_email()
