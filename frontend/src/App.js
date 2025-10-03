import React, { useState, useEffect, useRef, useCallback } from 'react';

// --- Helper Components ---
const AgentStep = ({ step, index }) => {
  const [isVisible, setIsVisible] = useState(false);
  const messageRef = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.1 }
    );

    if (messageRef.current) {
      observer.observe(messageRef.current);
    }

    return () => {
      if (messageRef.current) {
        observer.unobserve(messageRef.current);
      }
    };
  }, []);

  const getMessageType = () => {
    if (step.type === 'tool_call') return 'tool';
    if (step.message.startsWith('[')) return 'assistant';
    return 'user';
  };

  const messageType = getMessageType();
  
  const messageClasses = {
    assistant: 'bg-indigo-50 text-gray-800 border-l-4 border-indigo-500',
    tool: 'bg-blue-50 text-gray-800 border-l-4 border-blue-500',
    log: 'bg-gray-100 text-gray-600 text-sm italic',
    user: 'bg-white text-gray-800 border-l-4 border-gray-300',
  };

  const iconMap = {
    assistant: '🤖',
    tool: '⚙️',
    log: 'ℹ️',
    user: '👤',
  };

  const titleMap = {
    assistant: 'AI Assistant',
    tool: 'System',
    log: 'System',
    user: 'You',
  };

  return (
    <div 
      ref={messageRef}
      className={`transform transition-all duration-300 ease-in-out ${
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
      }`}
      style={{
        transitionDelay: `${index * 50}ms`,
      }}
    >
      <div className={`p-4 rounded-r-lg shadow-sm mb-4 ${messageClasses[messageType]}`}>
        <div className="flex items-center mb-1">
          <span className="text-lg mr-2">{iconMap[messageType]}</span>
          <span className="font-semibold text-sm text-gray-700">{titleMap[messageType]}</span>
          <span className="ml-auto text-xs text-gray-500">
            {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        <div className="whitespace-pre-wrap text-sm leading-relaxed pl-7">
          {step.message}
        </div>
      </div>
    </div>
  );
};

// --- Main App Component ---
function App() {
  const [clientId] = useState(() => `client_${Math.random().toString(36).substr(2, 9)}`);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const ws = useRef(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const typingTimeout = useRef(null);

  // --- WebSocket Connection ---
  useEffect(() => {
    if (ws.current) return;

    const connect = () => {
      ws.current = new WebSocket(`ws://127.0.0.1:8000/ws/${clientId}`);

      ws.current.onopen = () => {
        setIsConnected(true);
        setMessages([{ type: 'log', message: 'Connected to AI Assistant. How can I help you today?' }]);
      };

      ws.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.message.toLowerCase().includes('planner finished')) {
          setIsProcessing(false);
          setIsTyping(false);
        } else {
          setIsTyping(true);
          // Clear any existing timeout
          if (typingTimeout.current) clearTimeout(typingTimeout.current);
          // Set a new timeout
          typingTimeout.current = setTimeout(() => {
            setIsTyping(false);
          }, 2000);
        }
        setMessages(prev => [...prev, data]);
      };

      ws.current.onerror = (error) => {
        console.error("WebSocket Error: ", error);
        setMessages(prev => [...prev, {
          type: 'log', 
          message: 'Connection error. Please check if the backend is running.'
        }]);
      };

      ws.current.onclose = () => {
        setIsConnected(false);
        setIsProcessing(false);
        setIsTyping(false);
        setTimeout(connect, 3000);
      };
    };
    
    connect();

    return () => {
      if (ws.current) ws.current.close();
      if (typingTimeout.current) clearTimeout(typingTimeout.current);
    };
  }, [clientId]);
  
  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on load
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  // Handle sending messages
  const handleSend = useCallback(async () => {
    const message = input.trim();
    if (!message || !isConnected || isProcessing) return;
    
    // Add user message to the chat
    setMessages(prev => [...prev, { type: 'user', message }]);
    setInput('');
    setIsProcessing(true);
    setIsTyping(true);

    try {
      await fetch(`http://127.0.0.1:8000/instruct/${clientId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
    } catch (error) {
      console.error("Failed to send instruction:", error);
      setMessages(prev => [...prev, {
        type: 'log', 
        message: 'Error: Could not contact the backend.'
      }]);
      setIsProcessing(false);
      setIsTyping(false);
    }
  }, [input, isConnected, isProcessing, clientId]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Enter' && e.shiftKey) {
        // Shift + Enter for new line
        return;
      } else if (e.key === 'Enter' && !e.shiftKey) {
        // Just Enter to send
        e.preventDefault();
        handleSend();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSend]);

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 flex items-center justify-center mr-3">
              <span className="text-white font-bold text-sm">AI</span>
            </div>
            <h1 className="text-xl font-bold text-gray-800">AI Assistant</h1>
          </div>
          <div className="flex items-center">
            <div className={`w-2.5 h-2.5 rounded-full mr-2 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className="text-sm text-gray-600">
              {isConnected ? 'Connected' : 'Connecting...'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="flex-1 overflow-y-auto p-4 md:p-6 bg-gray-50">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mb-4">
                <span className="text-2xl">🤖</span>
              </div>
              <h2 className="text-xl font-semibold text-gray-800 mb-2">How can I help you today?</h2>
              <p className="text-gray-500 max-w-md">
                Ask me anything, from answering questions to helping with tasks, I'm here to assist you.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg, index) => (
                <AgentStep key={index} step={msg} index={index} />
              ))}
              {isTyping && (
                <div className="flex items-center p-4 bg-white rounded-lg shadow-sm border-l-4 border-indigo-200">
                  <div className="w-2 h-2 bg-indigo-400 rounded-full mr-1 animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-indigo-400 rounded-full mr-1 animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </main>

      {/* Input Area */}
      <footer className="bg-white border-t border-gray-200 py-4 px-4">
        <div className="max-w-3xl mx-auto">
          <div className="relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message here..."
              className="w-full px-4 py-3 pr-12 text-gray-800 bg-white border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
              rows="1"
              style={{ minHeight: '44px', maxHeight: '200px' }}
              onInput={(e) => {
                e.target.style.height = 'auto';
                e.target.style.height = (e.target.scrollHeight) + 'px';
              }}
              disabled={!isConnected || isProcessing}
            />
            <button
              onClick={handleSend}
              disabled={!isConnected || !input.trim() || isProcessing}
              className="absolute right-2 bottom-2 p-2 rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Send message"
            >
              <svg 
                className={`w-5 h-5 ${!input.trim() || !isConnected || isProcessing ? 'text-gray-400' : 'text-indigo-600 hover:text-indigo-700'}`} 
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24" 
                xmlns="http://www.w3.org/2000/svg"
              >
                <path 
                  strokeLinecap="round" 
                  strokeLinejoin="round" 
                  strokeWidth={2} 
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" 
                />
              </svg>
            </button>
          </div>
          <div className="mt-2 text-xs text-gray-500 text-center">
            {isConnected ? (
              <span className="flex items-center justify-center">
                <span className="w-2 h-2 rounded-full bg-green-500 mr-1.5"></span>
                Connected to AI Assistant
              </span>
            ) : (
              <span className="flex items-center justify-center">
                <span className="w-2 h-2 rounded-full bg-yellow-500 mr-1.5"></span>
                Connecting to server...
              </span>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;

