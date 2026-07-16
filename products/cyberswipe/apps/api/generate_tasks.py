import json
import random

def generate_tasks():
    quishing_scenarios = [
        ("Niedopłata za paczkę", "SMS", "high", "Dostałeś SMS o treści: 'Twoja paczka InPost została wstrzymana z powodu niedopłaty 1,50 PLN. Zeskanuj kod QR by opłacić.'", "Uważaj na fałszywe powiadomienia kurierskie.", "ignore", "Super! To klasyczny phishing kurierski (smishing).", "Błąd! Kurierzy nigdy nie proszą przez SMS o zeskanowanie QR do dopłat."),
        ("Bilet do kina", "Kino", "low", "Kupiłeś bilet do kina przez oficjalną aplikację. Przed ekranem widnieje kod QR do zeskanowania.", "Oficjalna apka ma mniejsze ryzyko.", "scan", "Dobrze, oficjalne aplikacje są weryfikowane.", "Nie musiałeś go ignorować, to zaufane źródło."),
        ("Darmowy Burger", "Ulica", "medium", "Na wiacie przystanku naklejono plakat 'Zeskanuj kod QR by odebrać darmowego burgera w McDonald!'. Kod wygląda na naklejony na coś innego.", "Zwróć uwagę na jakość i pochodzenie kodu.", "ignore", "Świetnie! Naklejone na plakaty kody często prowadzą do złośliwych stron.", "Źle! To Quishing. Naklejony luźno kod to red flag!"),
        ("Rachunek za prąd", "Skrzynka pocztowa", "high", "Dostałeś wydrukowaną kartkę o zaległości za prąd z kodem QR do szybkiej płatności blik. Wygląda podobnie do zwykłego rachunku, ale nie ma loga dostawcy.", "Brak logo lub dziwny format to częsty oszustwo.", "ignore", "Brawo! Fikcyjne faktury to popularny atak.", "Niestety, to scam udający pismo od PGE/Tauron."),
        ("Menu w restauracji", "Stolik w restauracji", "low", "Siedzisz w znanej kawiarni, na stole na stałe wklejony jest kod z napisem 'Menu'.", "Kody zatopione w materiale restauracji zazwyczaj są okej.", "scan", "Dobrze. W tej sytuacji to poprawny sposób otwarcia menu.", "Nie ma potrzeby go ignorować, jeśli nie jest to naklejka przyklejona brudnymi rękami."),
        ("Mandat za parkowanie", "Wycieraczka samochodu", "high", "Za wycieraczką leży wezwanie do zapłaty mandatu ze zdjęciem Twoich na lewo wklejonych blach i kodem QR.", "Urzędy nie zostawiają kodów QR do szybkich płatności za wycieraczką.", "ignore", "Doskonale. Straż Miejsca zostawia papierowy druk urzędowy, a nie kod do przelewu p2p.", "Zły wybór. Zapłaciłbyś oszustowi za rzekomy mandat."),
        ("Promocja na bilety", "Facebook", "medium", "Sponsorowany post kusi kodem QR dającym -90% na loty Ryanair. Profil ma 15 obserwujących.", "Podejrzanie niska cena i mały profil.", "ignore", "Słusznie, typowe naciąganie w oparciu o silne emocje 'okazji'.", "Błąd. To fake profil, który wykradnie Twoje dane."),
        ("Instrukcja pralki", "Dom", "low", "Kupiłeś nową pralkę w MediaMarkt, na jej panelu jest fabryczny kod QR z napisem 'Instrukcja obsługi wideo'.", "Kody prosto z fabryki w certyfikowanym sprzęcie.", "scan", "Poprawnie. Możesz bezpiecznie zeskanować taki fabryczny znak.", "Zignorowałeś przydatną funkcję z obawy na zapas."),
        ("Powiadomienie z banku", "Email", "high", "Email rzekomo od Twojego banku: 'Twoje konto zostanie zablokowane. Zeskanuj QR i zaloguj się by potwierdzić tożsamość.'", "Banki nigdy nie proszą o to przez email czy SMS.", "ignore", "Świetnie! To Quishing z groźbą zablokowania konta.", "To najgorszy z możliwych wyborów. Ostrzeże Cię to utratą konta!"),
        ("Hulajnoga miejska", "Chodnik", "medium", "Hulajnoga elektryczna z logo znanej marki, ale kod QR jest chropowaty i wygląda jak zaklejony innym, ciut większym kodem.", "Zwróć uwagę na strukturę naklejki.", "ignore", "Brawo! Oszuści naklejają fałszywe QR kody na miejskie rowery i hulajnogi.", "Podałbyś dane karty płatniczej oszustowi."),
    ]
    
    ai_scenarios = [
        ("Rozmowa Kwalifikacyjna", "LinkedIn", "Czy rekruter na zdjęciu jest prawdziwy? Zwróć uwagę na palce i tekstury ubrania.", "Włosy zlewające się z tłem to częsty błąd AI."),
        ("Ogłoszenie o Mieszkanie", "Olx", "Ktoś oferuje apartament za ułamek ceny. Jedno z tych zdjęć to fałszywe wnioskowanie wnętrza.", "Odbicia w lustrach często zdradzają AI."),
        ("Profil na Tinderze", "Aplikacja Randkowa", "Trafiłeś na super atrakcyjną parę. Które ze zdjęć wygenerowano żeby nakłonić Cię do oszukańczej konwersacji?", "Asymetria oczu i zębów ujawnia fałsz."),
        ("Relacja z powodzi", "Twitter", "Dezinformacyjny profil pokazuje straszną powódź. Znajdź obrazek wygenerowany przez sztuczną inteligencję.", "Brak realizmu w fizyce wody."),
        ("Oferta Pracy - Zespół", "Strona Firmy", "Fikcyjna agencja IT chwali się na stronie swoim zespołem. Wybierz 'pracownika' wykreowanego przez sieć GAN.", "Elementy tła i napisy w tle na zdjęciach AI bywają bezsensowne.")
    ]
    
    images_sets = [
        [
            "https://images.unsplash.com/photo-1549473889-14f410d83298?w=400&h=400&fit=crop", 
            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&h=400&fit=crop", 
            "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=400&h=400&fit=crop", 
            "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=400&h=400&fit=crop"
        ],
        [
            "https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?w=400&h=400&fit=crop",
            "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=400&fit=crop",
            "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=400&h=400&fit=crop",
            "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=400&fit=crop"
        ],
        [
            "https://images.unsplash.com/photo-1531427186611-ecfd6d936c79?w=400&h=400&fit=crop",
            "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400&h=400&fit=crop",
            "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=400&h=400&fit=crop",
            "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=400&fit=crop"
        ],
        [
            "https://images.unsplash.com/photo-1521119989659-a83eee488004?w=400&h=400&fit=crop",
            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&h=400&fit=crop",
            "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=400&fit=crop",
            "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=400&h=400&fit=crop"
        ]
    ]

    tasks = []
    task_id = 1
    
    # Generate 50 tasks (35 Quishing, 15 AI Image)
    # We will loop over base templates and randomize them slightly.
    quishing_count = 35
    ai_count = 15
    
    for i in range(quishing_count):
        base = random.choice(quishing_scenarios)
        tasks.append({
            "id": task_id,
            "type": "quishing",
            "title": f"{base[0]} #{i+1}",
            "location": base[1],
            "risk_level": base[2],
            "description": base[3],
            "hint": base[4],
            "correct_action": base[5],
            "explanation_correct": base[6],
            "explanation_incorrect": base[7]
        })
        task_id += 1
        
    for i in range(ai_count):
        base = random.choice(ai_scenarios)
        img_set = random.choice(images_sets)
        correct_img_idx = random.randint(1, 4)
        tasks.append({
            "id": task_id,
            "type": "ai_image",
            "title": f"{base[0]} #{i+1}",
            "location": base[1],
            "risk_level": "high",
            "description": base[2],
            "hint": base[3],
            "correct_action": f"image_{correct_img_idx}",
            "explanation_correct": "Dobre oko! To zdjęcie nosi ślady narzędzi tekst-to-image.",
            "explanation_incorrect": "Pudło. To prawdziwe zdjęcie, spójrz uważnie na brak artefaktów.",
            "images": img_set
        })
        task_id += 1

    # Shuffle everything for a random experience
    random.shuffle(tasks)
    
    # re-assign IDs incrementally so they appear 1 to 50
    for idx, t in enumerate(tasks):
        t["id"] = idx + 1

    with open("tasks.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=4, ensure_ascii=False)
        
    print(f"Generated {len(tasks)} tasks.")

if __name__ == "__main__":
    generate_tasks()
