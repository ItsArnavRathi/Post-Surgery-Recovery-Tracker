import React, { useState, useEffect } from 'react';
import { Upload, Camera, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, Activity, Clock, Ruler, Droplets } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';

// Mock Backend API - In production, this would be separate Flask backend
class MockBackendAPI {
  constructor() {
    this.woundHistory = [];
    this.currentAnalysis = null;
  }

  // Simulate wound analysis with computer vision models
  analyzeImage(imageFile) {
    return new Promise((resolve) => {
      setTimeout(() => {
        // Simulate advanced CV analysis results
        const mockAnalysis = {
          wound_id: `wound_${Date.now()}`,
          timestamp: new Date().toISOString(),
          image_metadata: {
            format: imageFile.type,
            size: imageFile.size,
            processed: true
          },
          wound_detection: {
            detected: true,
            confidence: 0.94,
            bounding_box: [120, 80, 300, 250]
          },
          wound_classification: {
            type: this.randomChoice(['surgical', 'diabetic_ulcer', 'pressure_ulcer', 'trauma']),
            confidence: 0.89,
            subtype: 'post_operative'
          },
          measurements: {
            area_cm2: this.randomFloat(2.5, 15.8),
            perimeter_cm: this.randomFloat(6.2, 18.4),
            depth_mm: this.randomFloat(0.8, 4.2),
            aspect_ratio: this.randomFloat(1.1, 2.3)
          },
          severity_assessment: {
            level: this.randomChoice(['mild', 'moderate', 'severe']),
            score: this.randomInt(20, 85),
            factors: ['tissue_quality', 'size', 'depth', 'location']
          },
          healing_stage: {
            current_stage: this.randomChoice(['hemostasis', 'inflammatory', 'proliferation', 'remodelling']),
            stage_confidence: 0.82,
            estimated_duration_days: this.randomInt(5, 21)
          },
          healing_score: this.randomInt(45, 92),
          infection_risk: {
            level: this.randomChoice(['low', 'medium', 'high']),
            risk_score: this.randomFloat(0.1, 0.8),
            indicators: {
              redness: this.randomFloat(0.2, 0.9),
              swelling: this.randomFloat(0.1, 0.7),
              discharge: this.randomFloat(0.0, 0.6),
              heat: this.randomFloat(0.1, 0.5),
              pain_likelihood: this.randomFloat(0.3, 0.8)
            },
            recommendation: 'Monitor closely, consider antibiotic prophylaxis if score increases'
          },
          temporal_analysis: {
            trend: this.randomChoice(['improving', 'worsening', 'unchanged']),
            healing_velocity: this.randomFloat(-0.3, 0.8),
            expected_recovery_days: this.randomInt(12, 45),
            comparison_available: this.woundHistory.length > 0
          },
          tissue_analysis: {
            granulation_percentage: this.randomFloat(45, 85),
            necrotic_tissue_percentage: this.randomFloat(0, 15),
            epithelialization_percentage: this.randomFloat(20, 70),
            exudate_level: this.randomChoice(['none', 'minimal', 'moderate', 'heavy'])
          },
          alerts: this.generateAlerts(),
          model_versions: {
            segmentation_model: 'DeepLabV3+_v2.1',
            classification_model: 'EfficientNet-B4_v1.3',
            temporal_model: 'LSTM_Transformer_v1.0'
          }
        };

        this.currentAnalysis = mockAnalysis;
        this.woundHistory.push({
          date: new Date().toLocaleDateString(),
          healing_score: mockAnalysis.healing_score,
          area: mockAnalysis.measurements.area_cm2,
          infection_risk: mockAnalysis.infection_risk.risk_score,
          stage: mockAnalysis.healing_stage.current_stage
        });

        resolve(mockAnalysis);
      }, 2000);
    });
  }

  getWoundHistory() {
    // Generate sample historical data
    const history = [];
    for (let i = 7; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      history.push({
        date: date.toLocaleDateString(),
        healing_score: this.randomInt(40 + i * 5, 60 + i * 6),
        area: this.randomFloat(12 - i * 0.8, 15 - i * 0.9),
        infection_risk: this.randomFloat(0.6 - i * 0.05, 0.8 - i * 0.06),
        stage: i < 2 ? 'inflammatory' : i < 5 ? 'proliferation' : 'remodelling'
      });
    }
    return [...history, ...this.woundHistory];
  }

  randomChoice(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  randomFloat(min, max) {
    return parseFloat((Math.random() * (max - min) + min).toFixed(2));
  }

  randomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  generateAlerts() {
    const alerts = [];
    if (Math.random() > 0.7) {
      alerts.push({
        type: 'warning',
        message: 'Increased redness detected - monitor for infection',
        severity: 'medium'
      });
    }
    if (Math.random() > 0.8) {
      alerts.push({
        type: 'info',
        message: 'Wound showing good granulation tissue development',
        severity: 'low'
      });
    }
    return alerts;
  }
}

const WoundAnalysisSystem = () => {
  const [selectedImage, setSelectedImage] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [activeTab, setActiveTab] = useState('upload');
  
  const mockAPI = new MockBackendAPI();

  useEffect(() => {
    // Load initial history data
    setHistory(mockAPI.getWoundHistory());
  }, []);

  const handleImageUpload = async (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedImage(URL.createObjectURL(file));
      setLoading(true);
      
      try {
        const result = await mockAPI.analyzeImage(file);
        setAnalysisResult(result);
        setHistory(mockAPI.getWoundHistory());
      } catch (error) {
        console.error('Analysis failed:', error);
      } finally {
        setLoading(false);
      }
    }
  };

  const getSeverityColor = (level) => {
    switch(level) {
      case 'low': return 'text-green-600 bg-green-100';
      case 'medium': return 'text-yellow-600 bg-yellow-100';
      case 'high': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStageColor = (stage) => {
    switch(stage) {
      case 'hemostasis': return 'bg-red-100 text-red-800';
      case 'inflammatory': return 'bg-orange-100 text-orange-800';
      case 'proliferation': return 'bg-blue-100 text-blue-800';
      case 'remodelling': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getTrendIcon = (trend) => {
    switch(trend) {
      case 'improving': return <TrendingUp className="text-green-600" />;
      case 'worsening': return <TrendingDown className="text-red-600" />;
      default: return <Activity className="text-yellow-600" />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">
            Post-Surgery Wound Analysis System
          </h1>
          <p className="text-lg text-gray-600">
          </p>
        </div>

        {/* Navigation Tabs */}
        <div className="flex justify-center mb-8">
          <div className="bg-white rounded-lg p-1 shadow-md">
            <button
              onClick={() => setActiveTab('upload')}
              className={`px-6 py-3 rounded-lg font-medium transition-all ${
                activeTab === 'upload'
                  ? 'bg-blue-500 text-white shadow-md'
                  : 'text-gray-600 hover:text-blue-500'
              }`}
            >
              <Upload className="inline mr-2 h-4 w-4" />
              Upload & Analyze
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`px-6 py-3 rounded-lg font-medium transition-all ${
                activeTab === 'history'
                  ? 'bg-blue-500 text-white shadow-md'
                  : 'text-gray-600 hover:text-blue-500'
              }`}
            >
              <Activity className="inline mr-2 h-4 w-4" />
              Healing Progress
            </button>
          </div>
        </div>

        {activeTab === 'upload' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Image Upload Section */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h3 className="text-xl font-semibold mb-4 flex items-center">
                <Camera className="mr-2 h-5 w-5 text-blue-500" />
                Wound Image Upload
              </h3>
              
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors">
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="hidden"
                  id="image-upload"
                />
                <label htmlFor="image-upload" className="cursor-pointer">
                  {selectedImage ? (
                    <div>
                      <img 
                        src={selectedImage} 
                        alt="Selected wound" 
                        className="max-h-64 mx-auto rounded-lg shadow-md mb-4"
                      />
                      <p className="text-sm text-gray-600">Click to select a different image</p>
                    </div>
                  ) : (
                    <div>
                      <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                      <p className="text-lg font-medium text-gray-700 mb-2">
                        Upload wound image
                      </p>
                      <p className="text-sm text-gray-500">
                        Supports JPEG, PNG, HEIC formats
                      </p>
                    </div>
                  )}
                </label>
              </div>

              {loading && (
                <div className="mt-4 text-center">
                  <div className="inline-flex items-center px-4 py-2 font-medium text-blue-600 bg-blue-100 rounded-lg">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
                    Analyzing image with AI models...
                  </div>
                </div>
              )}
            </div>

            {/* Analysis Results */}
            {analysisResult && (
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-xl font-semibold mb-4 flex items-center">
                  <CheckCircle className="mr-2 h-5 w-5 text-green-500" />
                  Analysis Results
                </h3>

                {/* Key Metrics */}
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">
                      {analysisResult.healing_score}/100
                    </div>
                    <div className="text-sm text-blue-700">Healing Score</div>
                  </div>
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <div className="text-lg font-bold text-purple-600">
                      {analysisResult.measurements.area_cm2} cm²
                    </div>
                    <div className="text-sm text-purple-700">Wound Area</div>
                  </div>
                </div>

                {/* Wound Classification */}
                <div className="mb-4">
                  <h4 className="font-semibold text-gray-700 mb-2">Classification</h4>
                  <div className="flex items-center space-x-4">
                    <span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
                      {analysisResult.wound_classification.type.replace('_', ' ')}
                    </span>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStageColor(analysisResult.healing_stage.current_stage)}`}>
                      {analysisResult.healing_stage.current_stage}
                    </span>
                  </div>
                </div>

                {/* Infection Risk */}
                <div className="mb-4">
                  <h4 className="font-semibold text-gray-700 mb-2">Infection Risk Assessment</h4>
                  <div className={`p-3 rounded-lg ${getSeverityColor(analysisResult.infection_risk.level)}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium">
                        {analysisResult.infection_risk.level.toUpperCase()} RISK
                      </span>
                      <span className="text-sm">
                        Score: {(analysisResult.infection_risk.risk_score * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Trend */}
                <div className="mb-4">
                  <h4 className="font-semibold text-gray-700 mb-2">Healing Trend</h4>
                  <div className="flex items-center space-x-2">
                    {getTrendIcon(analysisResult.temporal_analysis.trend)}
                    <span className="font-medium capitalize">
                      {analysisResult.temporal_analysis.trend}
                    </span>
                    <span className="text-sm text-gray-600">
                      (~{analysisResult.temporal_analysis.expected_recovery_days} days to heal)
                    </span>
                  </div>
                </div>

                {/* Alerts */}
                {analysisResult.alerts && analysisResult.alerts.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-gray-700 mb-2">Clinical Alerts</h4>
                    {analysisResult.alerts.map((alert, idx) => (
                      <div key={idx} className="flex items-start space-x-2 p-2 bg-yellow-50 border-l-4 border-yellow-400 rounded mb-2">
                        <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
                        <span className="text-sm text-yellow-800">{alert.message}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-xl font-semibold mb-6 flex items-center">
              <TrendingUp className="mr-2 h-5 w-5 text-blue-500" />
              Wound Healing Progress Over Time
            </h3>

            {/* Progress Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              <div>
                <h4 className="font-medium text-gray-700 mb-4">Healing Score Trend</h4>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Legend />
                    <Line 
                      type="monotone" 
                      dataKey="healing_score" 
                      stroke="#3B82F6" 
                      strokeWidth={3}
                      name="Healing Score"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div>
                <h4 className="font-medium text-gray-700 mb-4">Wound Area Reduction</h4>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line 
                      type="monotone" 
                      dataKey="area" 
                      stroke="#EF4444" 
                      strokeWidth={3}
                      name="Area (cm²)"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Infection Risk Chart */}
            <div className="mb-8">
              <h4 className="font-medium text-gray-700 mb-4">Infection Risk Assessment</h4>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis domain={[0, 1]} />
                  <Tooltip formatter={(value) => `${(value * 100).toFixed(1)}%`} />
                  <Bar dataKey="infection_risk" fill="#F59E0B" name="Infection Risk" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Summary Statistics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-green-50 p-4 rounded-lg text-center">
                <Clock className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <div className="text-2xl font-bold text-green-700">{history.length}</div>
                <div className="text-sm text-green-600">Days Tracked</div>
              </div>
              <div className="bg-blue-50 p-4 rounded-lg text-center">
                <TrendingUp className="h-8 w-8 text-blue-600 mx-auto mb-2" />
                <div className="text-2xl font-bold text-blue-700">
                  {history.length > 1 ? ((history[history.length-1]?.healing_score - history[0]?.healing_score) || 0) : 0}
                </div>
                <div className="text-sm text-blue-600">Score Improvement</div>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg text-center">
                <Ruler className="h-8 w-8 text-purple-600 mx-auto mb-2" />
                <div className="text-2xl font-bold text-purple-700">
                  {history.length > 1 ? ((history[0]?.area - history[history.length-1]?.area) || 0).toFixed(1) : '0.0'}
                </div>
                <div className="text-sm text-purple-600">Area Reduction (cm²)</div>
              </div>
              <div className="bg-orange-50 p-4 rounded-lg text-center">
                <Droplets className="h-8 w-8 text-orange-600 mx-auto mb-2" />
                <div className="text-2xl font-bold text-orange-700">
                  {history.length > 0 ? (history[history.length-1]?.infection_risk * 100 || 0).toFixed(0) : 0}%
                </div>
                <div className="text-sm text-orange-600">Current Risk Level</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WoundAnalysisSystem;
