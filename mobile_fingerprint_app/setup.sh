#!/bin/bash

# Mobile App Setup Script
# This script sets up the React Native fingerprint app for development

echo "🚀 Setting up Blockchain Fingerprint Mobile App..."

# Check if Node.js is installed
if ! command -v node &> /dev/null
then
    echo "❌ Node.js not found. Please install Node.js 16+ from https://nodejs.org"
    exit 1
fi

echo "✅ Node.js $(node --version) found"

# Check if npm is installed
if ! command -v npm &> /dev/null
then
    echo "❌ npm not found. Please install npm."
    exit 1
fi

echo "✅ npm $(npm --version) found"

# Install Expo CLI globally
echo "📦 Installing Expo CLI..."
npm install -g expo-cli

# Install dependencies
echo "📥 Installing project dependencies..."
npm install

# Create .env file if it doesn't exist
if [ ! -f .env ]
then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please update .env file with your backend URL!"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Update .env file with your backend URL:"
echo "     EXPO_PUBLIC_BACKEND_URL=http://YOUR_IP:5000/api"
echo ""
echo "  2. Start the app:"
echo "     npm start"
echo ""
echo "  3. Press 'a' to open on Android device/emulator"
echo ""
echo "🎉 Happy coding!"
