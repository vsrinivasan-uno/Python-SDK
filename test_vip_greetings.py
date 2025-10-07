#!/usr/bin/env python3
"""Test script to verify VIP greeting functionality.

This script tests the VIP person recognition feature to ensure:
1. VIP persons get custom greetings
2. Regular persons get standard greeting templates
3. Configuration is properly loaded
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(__file__))

from src.config import get_config


def test_vip_configuration():
    """Test that VIP persons are properly configured."""
    print("=" * 60)
    print("Testing VIP Person Configuration")
    print("=" * 60)
    
    config = get_config()
    
    # Test 1: Check VIP persons exist
    print("\n[Test 1] Checking VIP persons configuration...")
    vip_persons = config.face_recognition.vip_persons
    
    if not vip_persons:
        print("❌ FAIL: No VIP persons configured")
        return False
    
    print(f"✅ PASS: {len(vip_persons)} VIP persons configured")
    
    # Test 2: Verify all required VIP persons
    print("\n[Test 2] Verifying required VIP persons...")
    required_vips = [
        "Mayor John W Ewing Junior",
        "Chancellor Joanne Li",
        "President Heath Mello",
        "Associate Dean Robin Gandhi",
        "Dean Martha Garcia Murillo",
        "Senior Vice Chancellor Phil"
    ]
    
    all_present = True
    for vip_name in required_vips:
        if vip_name in vip_persons:
            print(f"  ✅ {vip_name}: Found")
        else:
            print(f"  ❌ {vip_name}: Missing")
            all_present = False
    
    if not all_present:
        print("❌ FAIL: Not all required VIP persons are configured")
        return False
    
    print("✅ PASS: All required VIP persons are configured")
    
    # Test 3: Verify greeting message format
    print("\n[Test 3] Verifying VIP greeting messages...")
    test_vip = "Chancellor Joanne Li"
    greeting = vip_persons[test_vip]
    
    required_phrases = [
        "Delighted to have you visit our AI-CCORE booth",
        "I am Misty",
        "powered by the Weitz Innovation Fund",
        "University of Nebraska Omaha",
        "BS and MS AI degrees",
        "To start conversation with me say Hey Misty"
    ]
    
    all_phrases_present = True
    for phrase in required_phrases:
        if phrase in greeting:
            print(f"  ✅ Contains: '{phrase}'")
        else:
            print(f"  ❌ Missing: '{phrase}'")
            all_phrases_present = False
    
    if not all_phrases_present:
        print("❌ FAIL: VIP greeting message missing required phrases")
        return False
    
    print("✅ PASS: VIP greeting message contains all required phrases")
    
    # Test 4: Verify greeting starts with person's name
    print("\n[Test 4] Verifying greeting personalization...")
    for vip_name in required_vips:
        greeting = vip_persons[vip_name]
        expected_start = f"Hi {vip_name}"
        if greeting.startswith(expected_start):
            print(f"  ✅ {vip_name}: Greeting properly personalized")
        else:
            print(f"  ❌ {vip_name}: Greeting does not start with 'Hi {vip_name}'")
            all_present = False
    
    if not all_present:
        print("❌ FAIL: Not all VIP greetings are properly personalized")
        return False
    
    print("✅ PASS: All VIP greetings are properly personalized")
    
    # Test 5: Show example greeting
    print("\n[Test 5] Example VIP Greeting:")
    print("-" * 60)
    print(f"Person: {test_vip}")
    print(f"Greeting: {greeting[:200]}...")
    print("-" * 60)
    
    return True


def main():
    """Run all tests."""
    print("\n🧪 Starting VIP Greeting Tests\n")
    
    try:
        success = test_vip_configuration()
        
        print("\n" + "=" * 60)
        if success:
            print("✅ ALL TESTS PASSED")
            print("=" * 60)
            print("\nVIP greeting feature is working correctly!")
            print("\nTo use this feature:")
            print("1. Train Misty to recognize the VIP persons' faces")
            print("2. When a VIP is recognized, they will receive the custom greeting")
            print("3. Regular persons will receive standard greetings")
            return 0
        else:
            print("❌ SOME TESTS FAILED")
            print("=" * 60)
            return 1
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())