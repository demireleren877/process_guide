#!/bin/bash

# Backend'i başlat
cd backend/app
python app.py &

# Frontend'i başlat
cd ../../frontend
npm run dev 