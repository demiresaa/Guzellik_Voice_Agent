# services/conversation_agent/cli.py

import sys
import os
# Ana dizin yapısına erişmek için
sys.path.append(os.path.join(os.path.dirname(__file__), '../..')) 

from .agent import ConversationAgent

def main():
    try:
        agent = ConversationAgent()
    except EnvironmentError as e:
        print(f"HATA: {e}")
        return

    print("\n--- Dağıtık Agent CLI Demo Başlangıcı ---")
    print("Booking Agent'ın (localhost:8001) çalıştığından emin olun!")
    print("\n[ASİSTAN]: Merhabalar Güzellik Merkezine hoş geldiniz, nasıl yardımcı olabilirim?")

    while True:
        try:
            user_input = input("\n[SEN]: ")
            if user_input.lower() == 'exit':
                break

            response = agent.converse(user_input)
            print(f"[ASİSTAN]: {response}")
            
        except Exception as e:
            print(f"\n[KRİTİK HATA]: Uygulama sırasında beklenmeyen bir hata oluştu: {e}")
            break

if __name__ == "__main__":
    main()