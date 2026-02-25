import logo from '../assets/logo.png'

export default function Logo() {
  return (
    <div
      className="
        h-11 w-11
        rounded-full
        bg-white
        shadow
        overflow-hidden
        flex items-center justify-center
      "
    >
      <img
        src={logo}
        alt="Dr Rania Said Functional Medicine"
        className="h-10 w-10 object-cover"
      />
    </div>
  )
}