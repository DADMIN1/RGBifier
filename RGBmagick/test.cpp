#include <iostream>
#include <Magick++.h>


extern "C" { // libRGBmagick.so exports //
void PythonPlz(const wchar_t ezString[]) { // easy for python, that is. python strings are UTF8 (wchar_t)
	std::cout << "\r"; // something must be written to std::cout before ever using std::wcout; otherwise,
	// output will never appear on std::cout!! (affects everything; executable and shared-library/FFI.py)
	std::wcout << L"  [PythonPlz]: " << ezString << std::endl;
}

int EpicFunction(int argc, const char* argv[]) {
	for (int C{0}; C < argc; C++) {
		std::cout << "  [EpicFunction]: ";
		std::cout << C << ": " << argv[C] << '\n';
	}
	return 69;
}
}// extern "C"


// stripped from library //
#ifndef IS_LIBRARY_BUILD
void PrintBuildInfo() {
	std::cout << "RGBmagick!!!";
	#ifdef MAGICKCORE_QUANTUM_DEPTH
	std::cout << " [QUANTUM_DEPTH: " << MAGICKCORE_QUANTUM_DEPTH << ']';
	#endif
	std::cout << '\n';
	
	#if MAGICKCORE_HDRI_ENABLE
	std::cout << "HDRI support enabled!!!\n";
	#endif
	
	#ifdef MAGICKCORE_MODULES_RELATIVE_PATH
	// I think this and a few other variables in "magick-config.h" should be defined...
	std::cout << "MAGICKCORE_MODULES_RELATIVE_PATH: " << MAGICKCORE_MODULES_RELATIVE_PATH << '\n';
	#endif
}

int main(int argc, const char* argv[])
{
	PrintBuildInfo();
	std::cout << "argc: " << argc << '\n';
	for (int C{0}; C < argc; C++) {
		std::cout << C << ": ";
		std::cout << argv[C] << '\n';
	}
	
	std::cout << '\n';
	PythonPlz(L"Plz Print This WideString Plz C++");
	EpicFunction(argc, argv);
	std::cout << '\n';
	
	std::cout << "testimages/peach.png\n";
	Magick::Image testimage("testimages/peach.png");
	std::cout << testimage.magick() << '\n'; // PNG
	std::cout << '[' << testimage.columns() << 'x' << testimage.rows() << "]\n";
	std::cout << std::endl;
	return 0;
}

#endif //NOT_LIBRARY_BUILD
