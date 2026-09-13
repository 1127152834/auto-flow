// Source: WebRPA@5ccb900e, components/ui/qq-contact-select.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useRef, useEffect } from 'react'
import { useGlobalConfigStore } from '../../hooks/stores/globalConfigStore'
import { ChevronDown, User, Users } from 'lucide-react'

interface QQContactSelectProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: 'all' | 'private' | 'group'  // 过滤类型
  className?: string
}

export function QQContactSelect({ 
  value, 
  onChange, 
  placeholder = '输入或选择QQ号/群号',
  type = 'all',
  className = ''
}: QQContactSelectProps) {
  const { config } = useGlobalConfigStore()
  const [isOpen, setIsOpen] = useState(false)
  const [inputValue, setInputValue] = useState(value)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // 过滤联系人
  const filteredContacts = (config.qq?.contacts || []).filter(contact => {
    if (type === 'all') return true
    return contact.type === type
  })

  // 同步外部 value 到内部 inputValue
  useEffect(() => {
    setInputValue(value)
  }, [value])

  // 点击外部关闭下拉框
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    setInputValue(newValue)
    onChange(newValue)
  }

  const handleSelectContact = (number: string) => {
    setInputValue(number)
    onChange(number)
    setIsOpen(false)
    inputRef.current?.focus()
  }

  const handleInputFocus = () => {
    if (filteredContacts.length > 0) {
      setIsOpen(true)
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          placeholder={placeholder}
          className={`w-full px-3 py-2 pr-8 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-black ${className}`}
        />
        {filteredContacts.length > 0 && (
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
          </button>
        )}
      </div>

      {/* 下拉列表 */}
      {isOpen && filteredContacts.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
          {filteredContacts.map((contact) => (
            <button
              key={contact.id}
              type="button"
              onClick={() => handleSelectContact(contact.number)}
              className="w-full px-3 py-2 text-left hover:bg-blue-50 transition-colors flex items-center gap-2 border-b border-gray-100 last:border-b-0"
            >
              {contact.type === 'group' ? (
                <Users className="w-4 h-4 text-green-600 flex-shrink-0" />
              ) : (
                <User className="w-4 h-4 text-blue-600 flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{contact.remark || contact.number}</span>
                  <span className="text-xs text-gray-400">
                    {contact.type === 'group' ? '群聊' : '私聊'}
                  </span>
                </div>
                {contact.remark && (
                  <div className="text-xs text-gray-500 truncate">{contact.number}</div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
