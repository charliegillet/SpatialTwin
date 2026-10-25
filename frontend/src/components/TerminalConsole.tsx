import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Trash2, Pause, Play, ShieldAlert, Cpu, Sparkles } from 'lucide-react';

export interface LogEntry {
  id: string;
  timestamp: string;
  category: 'SYS' | 'ARGON' | 'AGENT' | 'SOLVER' | 'HARDWARE';
  level: 'INFO' | 'WARN' | 'SUCCESS' | 'ALERT';
  message: string;
}

interface TerminalConsoleProps {
  logs: LogEntry[];
  onClear: () => void;
}

export const TerminalConsole: React.FC<TerminalConsoleProps> = ({ logs, onClear }) => {
  const [isPaused, setIsPaused] = useState(false);
  const [filter, setFilter] = useState<'ALL' | 'AI' | 'HW' | 'SOLVER'>('ALL');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (!isPaused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, isPaused]);

  const filteredLogs = logs.filter((log) => {
    if (filter === 'ALL') return true;
    if (filter === 'AI') return log.category === 'ARGON' || log.category === 'AGENT';
    if (filter === 'HW') return log.category === 'HARDWARE';
    if (filter === 'SOLVER') return log.category === 'SOLVER';
    return true;
  });

  const getCategoryColor = (cat: LogEntry['category']) => {
    switch (cat) {
      case 'ARGON':
        return 'text-cyan-400';
      case 'AGENT':
        return 'text-indigo-400';
      case 'SOLVER':
        return 'text-amber-400';
      case 'HARDWARE':
        return 'text-purple-400';
      default:
        return 'text-emerald-400';
    }
  };

  const getLevelColor = (lvl: LogEntry['level']) => {
    switch (lvl) {
      case 'ALERT':
        return 'text-rose-400 font-bold';
      case 'SUCCESS':
        return 'text-emerald-400 font-bold';
      case 'WARN':
        return 'text-amber-300 font-semibold';
      default:
        return 'text-emerald-500/90';
    }
  };

  return (
    <div className="relative w-full h-[290px] bg-[#02050b] rounded-xl border border-slate-800/90 flex flex-col overflow-hidden shadow-2xl font-mono">
      {/* Console Header Bar */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-950 border-b border-slate-800/80 text-xs">
        <div className="flex items-center space-x-2">
          <Terminal className="h-3.5 w-3.5 text-emerald-400" />
          <span className="font-bold text-slate-200 text-xs tracking-wider uppercase">
            Live System Telemetry Console
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/50">
            STREAMING (115200 BAUD)
          </span>
        </div>

        {/* Filter & Controls */}
        <div className="flex items-center space-x-2 text-[10px]">
          <div className="inline-flex rounded bg-slate-900 border border-slate-800 p-0.5">
            {(['ALL', 'AI', 'HW', 'SOLVER'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-2 py-0.5 rounded font-semibold transition ${
                  filter === f
                    ? 'bg-emerald-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          <button
            onClick={() => setIsPaused(!isPaused)}
            className="p-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800"
            title={isPaused ? 'Resume auto-scroll' : 'Pause auto-scroll'}
          >
            {isPaused ? <Play className="h-3 w-3 text-amber-400" /> : <Pause className="h-3 w-3" />}
          </button>

          <button
            onClick={onClear}
            className="p-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-rose-400 border border-slate-800"
            title="Clear console"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      </div>

      {/* Terminal Output Area (Phosphor Green Matrix look) */}
      <div
        ref={scrollRef}
        className="flex-1 p-3 overflow-y-auto space-y-1 text-[11px] leading-relaxed bg-[#02050b] select-text"
      >
        {filteredLogs.length === 0 ? (
          <div className="text-slate-600 italic py-4 text-center">
            [Telemetry stream initialized. Waiting for events...]
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} className="flex items-start space-x-2 hover:bg-slate-900/40 px-1 rounded">
              <span className="text-slate-600 select-none flex-shrink-0">[{log.timestamp}]</span>
              <span className={`font-bold flex-shrink-0 w-16 ${getCategoryColor(log.category)}`}>
                {log.category}:
              </span>
              <span className={`break-all ${getLevelColor(log.level)}`}>{log.message}</span>
            </div>
          ))
        )}
      </div>

      {/* Terminal Footer status */}
      <div className="px-3 py-1 bg-slate-950/90 border-t border-slate-900 text-[10px] text-slate-500 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Active Session • WebSocket/SSE Sync Monitored</span>
        </div>
        <span>{filteredLogs.length} Events Logged</span>
      </div>
    </div>
  );
};