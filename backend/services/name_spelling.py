"""
FR-13: Last Name Spelling and Verification
Spells out caller's last name using NATO phonetic alphabet for confirmation
"""

# NATO Phonetic Alphabet
NATO_PHONETIC = {
    'A': 'Alpha',
    'B': 'Bravo',
    'C': 'Charlie',
    'D': 'Delta',
    'E': 'Echo',
    'F': 'Foxtrot',
    'G': 'Golf',
    'H': 'Hotel',
    'I': 'India',
    'J': 'Juliet',
    'K': 'Kilo',
    'L': 'Lima',
    'M': 'Mike',
    'N': 'November',
    'O': 'Oscar',
    'P': 'Papa',
    'Q': 'Quebec',
    'R': 'Romeo',
    'S': 'Sierra',
    'T': 'Tango',
    'U': 'Uniform',
    'V': 'Victor',
    'W': 'Whiskey',
    'X': 'X-ray',
    'Y': 'Yankee',
    'Z': 'Zulu'
}

# Spanish phonetic alternatives (optional - use if caller is Spanish)
NATO_PHONETIC_ES = {
    'A': 'Antonio',
    'B': 'Barcelona',
    'C': 'Carmen',
    'D': 'Dolores',
    'E': 'Enrique',
    'F': 'Francisco',
    'G': 'Guatemala',
    'H': 'Historia',
    'I': 'Inés',
    'J': 'José',
    'K': 'Kilo',
    'L': 'Lorenzo',
    'M': 'María',
    'N': 'Navarra',
    'O': 'Oviedo',
    'P': 'París',
    'Q': 'Querétaro',
    'R': 'Ramón',
    'S': 'Santiago',
    'T': 'Tarragona',
    'U': 'Ulises',
    'V': 'Valencia',
    'W': 'Washington',
    'X': 'Xilófono',
    'Y': 'Yegua',
    'Z': 'Zaragoza'
}


def split_full_name(full_name: str) -> tuple[str, str]:
    """
    Split full name into first and last name.
    
    Args:
        full_name: Full name string (e.g., "Emma Prischak")
        
    Returns:
        (first_name, last_name) tuple
        
    Examples:
        "Emma Prischak" -> ("Emma", "Prischak")
        "John Smith Jr." -> ("John", "Smith Jr.")
        "Maria" -> ("Maria", "")
    """
    parts = full_name.strip().split()
    
    if len(parts) == 0:
        return "", ""
    elif len(parts) == 1:
        return parts[0], ""
    else:
        # First word is first name, rest is last name
        first_name = parts[0]
        last_name = " ".join(parts[1:])
        return first_name, last_name


def spell_name_phonetically(name: str, language: str = "en") -> str:
    """
    Convert a name to phonetic spelling using NATO alphabet.
    
    Args:
        name: Name to spell out (e.g., "Prischak")
        language: 'en' for English NATO, 'es' for Spanish phonetic
        
    Returns:
        Phonetic spelling string
        
    Examples:
        "Smith" -> "S as in Sierra, M as in Mike, I as in India, 
                    T as in Tango, H as in Hotel"
        "García" -> "G as in Golf, A as in Alpha, R as in Romeo, 
                     C as in Charlie, I as in India, A as in Alpha"
    """
    if not name:
        return ""
    
    # Choose alphabet based on language
    alphabet = NATO_PHONETIC_ES if language == 'es' else NATO_PHONETIC
    
    # Clean the name - remove special characters, keep only letters
    name_clean = name.upper()
    
    phonetic_parts = []
    for char in name_clean:
        if char in alphabet:
            phonetic_parts.append(f"{char} as in {alphabet[char]}")
        elif char == ' ':
            phonetic_parts.append("space")
        elif char == '-':
            phonetic_parts.append("hyphen")
        elif char == "'":
            phonetic_parts.append("apostrophe")
        # Skip other special characters
    
    return ", ".join(phonetic_parts)


def generate_spelling_confirmation(full_name: str, language: str = "en", use_nato: bool = False) -> str:
    """
    Generate the full spelling confirmation phrase for Nova to say.
    
    Args:
        full_name: Full name to spell (e.g., "Emma Prischak")
        language: 'en' or 'es'
        use_nato: If True, use NATO phonetic. If False, just spell letters.
        
    Returns:
        Complete phrase for Nova to say
        
    Examples:
        Simple spelling: "Let me spell that: P-R-I-S-C-H-A-K. Did I get that right?"
        NATO spelling: "Let me spell that back to you: P as in Papa, R as in Romeo..."
    """
    first_name, last_name = split_full_name(full_name)
    
    if not last_name:
        # Only first name provided - don't spell
        return ""
    
    if use_nato:
        # Use NATO phonetic alphabet (for clarity when confused)
        phonetic_spelling = spell_name_phonetically(last_name, language)
        
        if language == 'es':
            return (
                f"Déjame deletrear tu apellido con el alfabeto fonético: {phonetic_spelling}. "
                f"¿Lo tengo bien ahora?"
            )
        else:
            return (
                f"Let me spell that using the phonetic alphabet: {phonetic_spelling}. "
                f"Did I get that right?"
            )
    else:
        # Simple letter-by-letter spelling
        letters = "-".join(last_name.upper())
        
        if language == 'es':
            return (
                f"Déjame deletrear tu apellido: {letters}. ¿Lo tengo bien?"
            )
        else:
            return (
                f"Let me spell that last name: {letters}. Did I get that right?"
            )


def detect_spelling_correction(user_input: str) -> bool:
    """
    Detect if user is saying the spelling is wrong.
    
    Args:
        user_input: What the caller said
        
    Returns:
        True if they're indicating the spelling is wrong
    """
    user_lower = user_input.lower()
    
    # Negative responses
    negative_indicators = [
        "no", "nope", "wrong", "incorrect", "not right",
        "that's not it", "not quite", "actually",
        # Spanish
        "no", "incorrecto", "mal", "no está bien"
    ]
    
    return any(indicator in user_lower for indicator in negative_indicators)


def generate_correction_request(language: str = "en") -> str:
    """
    Ask the user to spell their name letter by letter.
    
    Args:
        language: 'en' or 'es'
        
    Returns:
        Phrase asking for correction
    """
    if language == 'es':
        return "Discúlpame. ¿Puedes deletrear tu apellido letra por letra?"
    else:
        return "My apologies. Can you spell your last name for me, letter by letter?"


def extract_spelled_name(user_input: str) -> str:
    """
    Extract spelled-out name from user's letter-by-letter spelling.
    
    Args:
        user_input: User saying letters (e.g., "P R I S C H A K")
        
    Returns:
        Reconstructed name
        
    Examples:
        "P R I S C H A K" -> "PRISCHAK"
        "S M I T H" -> "SMITH"
        "A as in apple, B as in boy, C as in cat" -> "ABC"
    """
    # Remove common filler words
    cleaned = user_input.upper()
    for filler in [" AS IN ", " LIKE ", " FOR ", " DE "]:
        cleaned = cleaned.replace(filler, " ")
    
    # Extract just the letters
    letters = []
    for word in cleaned.split():
        # Take first letter of each word
        if word and word[0].isalpha():
            letters.append(word[0])
    
    return "".join(letters)


# ── Example usage ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test cases
    test_names = [
        "Emma Prischak",
        "John Smith",
        "María García",
        "O'Connor",
        "Jean-Claude Van Damme"
    ]
    
    print("English NATO Phonetic Examples:")
    print("=" * 60)
    for name in test_names:
        confirmation = generate_spelling_confirmation(name, "en")
        if confirmation:
            print(f"\n{name}:")
            print(f"  {confirmation}")
    
    print("\n\nSpanish Phonetic Examples:")
    print("=" * 60)
    for name in test_names:
        confirmation = generate_spelling_confirmation(name, "es")
        if confirmation:
            print(f"\n{name}:")
            print(f"  {confirmation}")
    
    # Test correction detection
    print("\n\nCorrection Detection Tests:")
    print("=" * 60)
    test_responses = [
        "Yes, that's right",
        "No, that's wrong",
        "Actually, it's spelled differently",
        "Nope"
    ]
    for response in test_responses:
        is_wrong = detect_spelling_correction(response)
        print(f"{response} -> Wrong? {is_wrong}")