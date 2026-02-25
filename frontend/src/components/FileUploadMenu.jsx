export default function FileUploadMenu({ onSelect }) {
  return (
    <div className="absolute bottom-14 left-4 bg-white shadow rounded-lg overflow-hidden">
      <button onClick={() => onSelect('file')} className="block px-4 py-2 hover:bg-slate-100">Upload Report</button>
      <button onClick={() => onSelect('appointment')} className="block px-4 py-2 hover:bg-slate-100">Book Appointment</button>
    </div>
  )
}